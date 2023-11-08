"""Train a neural network to perform energy disaggregation.

Given a sequence of electricity mains reading, the algorithm
separates the mains into appliances.

Copyright (c) 2022~2023 Lindo St. Angel
"""

import os
import argparse
import socket

import tensorflow as tf
import tensorflow_model_optimization as tfmot
from keras import mixed_precision
import matplotlib.pyplot as plt

import define_models
from logger import Logger
import common

# Specify model architecture to use for training.
# MODEL_ARCH = "transformer_fit"
MODEL_ARCH = "cnn"
model_archs = dir(define_models)
if MODEL_ARCH not in model_archs:
    raise ValueError(f"Unknown model architecture: {MODEL_ARCH}!")
else:
    print(f"Using model architecture: {MODEL_ARCH}.")

### DO NOT USE MIXED-PRECISION - CURRENTLY GIVES POOR MODEL ACCURACY ###
# TODO: fix.
# Run in mixed-precision mode for ~30% speedup vs TensorFloat-32
# w/GPU compute capability = 8.6.
# mixed_precision.set_global_policy('mixed_float16')

# Set to True run in TF eager mode for debugging.
# May have to reduce batch size <= 512 to avoid OOM.
RUN_EAGERLY = False


def smooth_curve(points, factor=0.8):
    """Smooth a series of points given a smoothing factor."""
    smoothed_points = []
    for point in points:
        if smoothed_points:
            previous = smoothed_points[-1]
            smoothed_points.append(previous * factor + point * (1 - factor))
        else:
            smoothed_points.append(point)
    return smoothed_points


def plot(history, plot_name, plot_display, appliance_name):
    """Save and display loss and mae plots."""
    # Mean square error.
    loss = history.history["loss"]
    val_loss = history.history["val_loss"]
    plot_epochs = range(1, len(loss) + 1)
    plt.plot(plot_epochs, smooth_curve(loss), label="Smoothed Training Loss")
    plt.plot(plot_epochs, smooth_curve(val_loss), label="Smoothed Validation Loss")
    plt.title(f"Training history for {appliance_name} ({plot_name})")
    plt.ylabel("Loss (MSE)")
    plt.xlabel("Epoch")
    plt.legend()
    plot_filepath = os.path.join(args.save_dir, appliance_name, f"{plot_name}_loss")
    log(f"Plot directory: {plot_filepath}")
    plt.savefig(fname=plot_filepath)
    if plot_display:
        plt.show()
    plt.close()
    # Mean Absolute Error.
    val_mae = history.history["val_mae"]
    plt.plot(plot_epochs, smooth_curve(val_mae))
    plt.title(f"Smoothed validation MAE for {appliance_name} ({plot_name})")
    plt.ylabel("Mean Absolute Error")
    plt.xlabel("Epoch")
    plot_filepath = os.path.join(args.save_dir, appliance_name, f"{plot_name}_mae")
    log(f"Plot directory: {plot_filepath}")
    plt.savefig(fname=plot_filepath)
    if plot_display:
        plt.show()
    plt.close()


def get_arguments():
    parser = argparse.ArgumentParser(
        description="Train a neural network for energy disaggregation - \
            network input = mains window; network target = the states of \
            the target appliance."
    )
    parser.add_argument(
        "--appliance_name",
        type=str,
        default="kettle",
        help="the name of target appliance",
    )
    parser.add_argument(
        "--datadir",
        type=str,
        default="./dataset_management/refit",
        help="this is the directory of the training samples",
    )
    parser.add_argument(
        "--save_dir",
        type=str,
        default="./models",
        help="this is the directory to save the trained models",
    )
    parser.add_argument(
        "--prune_log_dir",
        type=str,
        default="./pruning_logs",
        help="location of pruning logs",
    )
    parser.add_argument(
        "--batchsize",
        type=int,
        default=1024,
        help="The batch size of training examples",
    )
    parser.add_argument("--n_epoch", type=int, default=50, help="The number of epochs.")
    parser.add_argument(
        "--prune_end_epoch",
        type=int,
        default=15,
        help="The number of epochs to prune over.",
    )
    parser.add_argument(
        "--crop_train_dataset",
        type=int,
        default=None,
        help="Number of train samples to use. Default uses entire dataset.",
    )
    parser.add_argument(
        "--crop_val_dataset",
        type=int,
        default=None,
        help="Number of val samples to use. Default uses entire dataset.",
    )
    parser.add_argument(
        "--qat",
        action="store_true",
        help="Fine-tune pre-trained model with quantization aware training.",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Prune pre-trained model for on-device inference.",
    )
    parser.add_argument(
        "--train", action="store_true", help="If set, train model from scratch."
    )
    parser.add_argument("--plot", action="store_true", help="If set, display plots.")
    parser.set_defaults(plot=False)
    parser.set_defaults(qat=False)
    parser.set_defaults(prune=False)
    parser.set_defaults(train=False)
    return parser.parse_args()


class TransformerCustomSchedule(tf.keras.optimizers.schedules.LearningRateSchedule):
    """Learning rate scheduler per Attention Is All You Need"""

    def __init__(self, d_model, warmup_steps=4000):
        super().__init__()

        self.d_model = d_model
        self.d_model_f = tf.cast(self.d_model, tf.float32)

        self.warmup_steps = warmup_steps

    def __call__(self, step):
        step = tf.cast(step, dtype=tf.float32)
        arg1 = tf.math.rsqrt(step)
        arg2 = step * (self.warmup_steps**-1.5)

        return tf.math.rsqrt(self.d_model_f) * tf.math.minimum(arg1, arg2)

    def get_config(self):
        config = {"d_model": self.d_model, "warmup_steps": self.warmup_steps}
        return config


def decay_custom_schedule(
    batches_per_epoch: int, epochs_per_decay_step: int = 5
) -> tf.keras.optimizers.schedules:
    """Decay lr at 1/t every 'epochs_per_decay_step' epochs.

    Typically set batches_per_epoch = training_provider.__len__()
    """
    return tf.keras.optimizers.schedules.InverseTimeDecay(
        0.001,
        decay_steps=batches_per_epoch * epochs_per_decay_step,
        decay_rate=1,
        staircase=False,
    )


if __name__ == "__main__":
    args = get_arguments()
    logger = Logger(
        os.path.join(
            args.save_dir,
            args.appliance_name,
            f"{args.appliance_name}_{MODEL_ARCH}.log",
        )
    )
    logger.log(f"Machine name: {socket.gethostname()}")
    logger.log(f"tf version: {tf.version.VERSION}")
    logger.log("Arguments: ")
    logger.log(args)

    # The appliance to train on.
    appliance_name = args.appliance_name
    logger.log(f"Appliance name: {appliance_name}")

    batch_size = args.batchsize
    logger.log(f"Batch size: {batch_size}")

    window_length = common.params_appliance[appliance_name]["window_length"]
    logger.log(f"Window length: {window_length}")

    # Path for training data.
    training_path = os.path.join(
        args.datadir, appliance_name, f"{appliance_name}_training_.csv"
    )
    logger.log(f"Training dataset: {training_path}")

    # Look for the validation set
    for filename in os.listdir(os.path.join(args.datadir, appliance_name)):
        if "validation" in filename:
            val_filename = filename
    # path for validation data
    validation_path = os.path.join(args.datadir, appliance_name, val_filename)
    logger.log(f"Validation dataset: {validation_path}")

    model_filepath = os.path.join(args.save_dir, appliance_name)
    logger.log(f"Model file path: {model_filepath}")

    savemodel_filepath = os.path.join(model_filepath, f"savemodel_{MODEL_ARCH}")
    logger.log(f"Savemodel file path: {savemodel_filepath}")

    # Load datasets.
    train_dataset = common.load_dataset(training_path, args.crop_train_dataset)
    val_dataset = common.load_dataset(validation_path, args.crop_val_dataset)
    num_train_samples = train_dataset[0].size
    logger.log(f"There are {num_train_samples/10**6:.3f}M training samples.")
    num_val_samples = val_dataset[0].size
    logger.log(f"There are {num_val_samples/10**6:.3f}M validation samples.")

    # Init window generator to provide samples and targets.
    WindowGenerator = common.get_window_generator()
    training_provider = WindowGenerator(
        dataset=train_dataset,
        batch_size=batch_size,
        window_length=window_length,
        p=None,
    )  # if MODEL_ARCH!='transformer' else 0.2)
    validation_provider = WindowGenerator(
        dataset=val_dataset,
        batch_size=batch_size,
        window_length=window_length,
        shuffle=False,
    )

    early_stopping = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=6, verbose=2
    )

    """***************** 參數設定完成，開始特定Train *******************"""
    if args.train:
        logger.log("Training model from scratch.")

        if MODEL_ARCH == "transformer":
            raise ValueError(
                'Must use model "transformer_fit" for training with .fit().'
            )
        elif MODEL_ARCH == "transformer_fit":
            # Calculate normalized threshold for appliance status determination.
            threshold = common.params_appliance[appliance_name]["on_power_threshold"]
            max_on_power = common.params_appliance[appliance_name]["max_on_power"]
            threshold /= max_on_power
            logger.log(f"Normalized on power threshold: {threshold}")

            # Get L1 loss multiplier.
            c0 = common.params_appliance[appliance_name]["c0"]
            logger.log(f"L1 loss multiplier: {c0}")

            model_depth = 256
            model = define_models.transformer_fit(
                window_length=window_length,
                threshold=threshold,
                d_model=model_depth,
                c0=c0,
            )
            # lr_schedule = TransformerCustomSchedule(d_model=model_depth)
            lr_schedule = 1e-4
        elif MODEL_ARCH == "cnn":
            # model = define_models.cnn(window_length=window_length)
            model = define_models.cnn()
            lr_schedule = 1e-4
        elif MODEL_ARCH == "fcn":
            model = define_models.fcn(window_length=window_length)
            lr_schedule = 1e-4
        elif MODEL_ARCH == "resnet":
            model = define_models.resnet(window_length=window_length)
            lr_schedule = 1e-4

        model.compile(
            optimizer=tf.keras.optimizers.Adam(
                learning_rate=lr_schedule, beta_1=0.9, beta_2=0.999, epsilon=1e-08
            ),
            loss="mse",
            metrics=["msle", "mae"],
            run_eagerly=RUN_EAGERLY,
        )

        checkpoint_callback = tf.keras.callbacks.ModelCheckpoint(
            filepath=savemodel_filepath,
            monitor="val_loss",
            verbose=1,
            save_best_only=True,
            mode="auto",
            save_freq="epoch",
        )

        callbacks = [early_stopping, checkpoint_callback]

        history = model.fit(
            x=training_provider,
            steps_per_epoch=None,
            epochs=args.n_epoch,
            callbacks=callbacks,
            validation_data=validation_provider,
            validation_steps=None,
            workers=24,
            use_multiprocessing=True,
        )

        model.summary()

        plot(
            history,
            plot_name=f"train_{MODEL_ARCH}",
            plot_display=args.plot,
            appliance_name=appliance_name,
        )
    elif args.qat:
        logger.log("Fine-tuning pre-trained model with quantization aware training.")

        quantize_model = tfmot.quantization.keras.quantize_model

        model = tf.keras.models.load_model(savemodel_filepath)

        q_aware_model = quantize_model(model)

        q_aware_model.compile(
            optimizer=tf.keras.optimizers.Adam(
                learning_rate=0.0001, beta_1=0.9, beta_2=0.999, epsilon=1e-08
            ),
            loss="mse",
            metrics=["mse", "msle", "mae"],
        )

        q_aware_model.summary()

        q_checkpoint_filepath = os.path.join(model_filepath, "qat_checkpoints")
        logger.log(f"QAT checkpoint file path: {q_checkpoint_filepath}")

        q_checkpoint_callback = tf.keras.callbacks.ModelCheckpoint(
            filepath=q_checkpoint_filepath,
            monitor="val_mse",
            verbose=1,
            save_best_only=True,
            mode="auto",
            save_freq="epoch",
        )

        callbacks = [early_stopping, q_checkpoint_callback]

        history = q_aware_model.fit(
            x=training_provider,
            steps_per_epoch=None,
            epochs=args.n_epoch,
            callbacks=callbacks,
            validation_data=validation_provider,
            validation_steps=None,
            workers=24,
            use_multiprocessing=True,
        )

        plot(
            history,
            plot_name=f"qat_{MODEL_ARCH}",
            plot_display=args.plot,
            appliance_name=appliance_name,
        )
    elif args.prune:
        logger.log("Prune pre-trained model for on-device inference.")

        model = tf.keras.models.load_model(savemodel_filepath)

        # Compute end step to finish pruning after 15 epochs.
        end_step = (num_train_samples // args.batchsize) * args.prune_end_epoch

        # Define parameters for pruning.
        pruning_params = {
            "pruning_schedule": tfmot.sparsity.keras.PolynomialDecay(
                initial_sparsity=0.25,
                final_sparsity=0.75,
                begin_step=0,
                end_step=end_step,
            )
        }

        # Sparsifies the layer's weights during training.
        prune_low_magnitude = tfmot.sparsity.keras.prune_low_magnitude

        # Try to apply pruning wrapper with pruning policy parameter.
        try:
            model_for_pruning = prune_low_magnitude(model, **pruning_params)
        except ValueError as e:
            logger.log(e, level="error")
            exit()

        model_for_pruning.compile(
            optimizer=tf.keras.optimizers.Adam(
                learning_rate=0.0001,  # lower rate than training from scratch
                beta_1=0.9,
                beta_2=0.999,
                epsilon=1e-08,
            ),
            loss="mse",
            metrics=["mse", "msle", "mae"],
        )

        model_for_pruning.summary()

        pruning_checkpoint_filepath = os.path.join(
            model_filepath, f"pruning_checkpoints_{MODEL_ARCH}"
        )
        logger.log(f"Pruning checkpoint file path: {pruning_checkpoint_filepath}")

        pruning_checkpoint_callback = tf.keras.callbacks.ModelCheckpoint(
            filepath=pruning_checkpoint_filepath,
            monitor="val_mse",
            verbose=1,
            save_best_only=True,
            mode="auto",
            save_freq="epoch",
        )

        pruning_callbacks = [
            pruning_checkpoint_callback,
            tfmot.sparsity.keras.UpdatePruningStep(),
            tfmot.sparsity.keras.PruningSummaries(log_dir=args.prune_log_dir),
        ]

        history = model_for_pruning.fit(
            x=training_provider,
            steps_per_epoch=None,
            epochs=args.prune_end_epoch,
            callbacks=pruning_callbacks,
            validation_data=validation_provider,
            validation_steps=None,
            workers=24,
            use_multiprocessing=True,
        )

        plot(
            history,
            plot_name=f"prune_{MODEL_ARCH}",
            plot_display=args.plot,
            appliance_name=appliance_name,
        )

        model_for_pruning.summary()

        pruned_model_filepath = os.path.join(
            model_filepath, f"pruned_model_{MODEL_ARCH}"
        )
        logger.log(f"Final pruned model file path: {pruned_model_filepath}")
        model_for_pruning.save(pruned_model_filepath)

        model_for_export = tfmot.sparsity.keras.strip_pruning(model_for_pruning)
        model_for_export.summary()

        pruned_model_for_export_filepath = os.path.join(
            model_filepath, f"pruned_model_for_export_{MODEL_ARCH}"
        )
        logger.log(
            f"Pruned model for export file path: {pruned_model_for_export_filepath}"
        )
        model_for_export.save(pruned_model_for_export_filepath)
    else:
        print("Nothing was done, train, qat or prune must be selected.")
