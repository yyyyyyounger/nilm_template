"""Various common functions and parameters.

Copyright (c) 2022, 2023 Lindo St. Angel.
"""

import os
import pandas as pd
import time

import numpy as np
from tqdm import tqdm

# Alternative aggregate standardization parameters used for all appliances.
# From Michele D’Incecco, et. al., "Transfer Learning for Non-Intrusive Load Monitoring"
ALT_AGGREGATE_MEAN = 522.0  # in Watts
ALT_AGGREGATE_STD = 814.0  # in Watts

# If True the alternative standardization parameters will be used
# for scaling the datasets.
USE_ALT_STANDARDIZATION = True

# If True the appliance dataset will be normalized to [0, max_on_power]
# else the appliance dataset will be z-score standardized.
USE_APPLIANCE_NORMALIZATION = True

# Power consumption sample update period in seconds.
SAMPLE_PERIOD = 8

# Various parameters used for training, validation and testing.
# Except where noted, values are calculated from statistical analysis
# of the respective dataset.
params_appliance = {
    "kettle": {
        # Input sample window length (samples).
        "window_length": 599,
        # Appliance considered inactive below this power draw (W).
        # From Zhenrui Yue, et. al., "BERT4NILM: A Bidirectional Transformer Model
        # for Non-Intrusive Load Monitoring".
        "on_power_threshold": 2000.0,
        # Appliance max power draw (W).
        # From Zhenrui Yue, et. al., "BERT4NILM: A Bidirectional Transformer Model
        # for Non-Intrusive Load Monitoring".
        "max_on_power": 3100,  # 3998.0,
        # Appliance power draw considered invalid longer than this value (s).
        # From Zhenrui Yue, et. al., "BERT4NILM: A Bidirectional Transformer Model
        # for Non-Intrusive Load Monitoring".
        "min_on_duration": 12.0,
        # Appliance power draw considered invalid if shorter than this value (s).
        # From Zhenrui Yue, et. al., "BERT4NILM: A Bidirectional Transformer Model
        # for Non-Intrusive Load Monitoring".
        "min_off_duration": 0.0,
        # Training aggregate dataset mean (W).
        "train_agg_mean": 501.32453633286167,
        # Training aggregate dataset standard deviation (W).
        "train_agg_std": 783.0367822932175,
        # Training appliance dataset mean (W).
        "train_app_mean": 16.137261776311778,
        # Training appliance dataset standard deviation (W).
        "train_app_std": 196.89790951996966,
        # Test appliance dataset mean (W).
        "test_app_mean": 23.155018918550294,
        # Test aggregate dataset mean (W)
        "test_agg_mean": 465.10226795866976,
        # Appliance dataset alternative standardization mean (W).
        # From Michele D’Incecco, et. al., "Transfer Learning for
        # Non-Intrusive Load Monitoring"
        "alt_app_mean": 700.0,
        # Appliance dataset alternative standardization std (W).
        # From Michele D’Incecco, et. al., "Transfer Learning for
        # Non-Intrusive Load Monitoring"
        "alt_app_std": 1000.0,
        # Coefficient 0 (L1 loss multiplier).
        # From Zhenrui Yue, et. al., "BERT4NILM: A Bidirectional Transformer Model
        # for Non-Intrusive Load Monitoring".
        "c0": 1.0,
    },
    "microwave": {
        "window_length": 599,
        "on_power_threshold": 200.0,
        "max_on_power": 3000.0,
        "min_on_duration": 12.0,
        "min_off_duration": 30.0,
        "train_agg_mean": 495.0447502551665,
        "train_agg_std": 704.1066664964247,
        "train_app_mean": 3.4617193220425304,
        "train_app_std": 64.22826568216946,
        "test_app_mean": 9.577146165430394,
        "test_agg_mean": 381.2162070293207,
        "alt_app_mean": 500.0,
        "alt_app_std": 800.0,
        "c0": 1.0,
    },
    "fridge": {
        "window_length": 599,
        "on_power_threshold": 50.0,
        "max_on_power": 400.0,
        "min_on_duration": 60.0,
        "min_off_duration": 12.0,
        "train_agg_mean": 605.4483277115743,
        "train_agg_std": 952.1533235759814,
        "train_app_mean": 48.55206460642049,
        "train_app_std": 62.114631485397986,
        "test_app_mean": 24.40792692094185,
        "test_agg_mean": 254.83458540217833,
        "alt_app_mean": 200.0,
        "alt_app_std": 400.0,
        "c0": 1e-06,
    },
    "dishwasher": {
        "window_length": 599,
        "on_power_threshold": 10.0,
        "max_on_power": 2500.0,
        "min_on_duration": 1800.0,
        "min_off_duration": 1800.0,
        "train_agg_mean": 606.3228537145152,
        "train_agg_std": 833.611776395652,
        "train_app_mean": 46.040618889481905,
        "train_app_std": 305.87980576285474,
        "test_app_mean": 11.299554135013219,
        "test_agg_mean": 377.9968064884045,
        "alt_app_mean": 700.0,
        "alt_app_std": 1000.0,
        "c0": 1.0,
    },
    "washingmachine": {
        "window_length": 599,
        "on_power_threshold": 20.0,
        "max_on_power": 2500.0,
        "min_on_duration": 1800.0,
        "min_off_duration": 160.0,
        "train_agg_mean": 517.5859340919116,
        "train_agg_std": 827.1565574135092,
        "train_app_mean": 22.22078550102201,
        "train_app_std": 189.70389890256996,
        "test_app_mean": 29.433812118685246,
        "test_agg_mean": 685.6151694157477,
        "alt_app_mean": 400.0,
        "alt_app_std": 700.0,
        "c0": 1e-02,
    },
}


def find_test_filename(test_dir, appliance, test_type) -> str:
    """Find test file name given a datset name."""
    for filename in os.listdir(os.path.join(test_dir, appliance)):
        if test_type == "train" and "TRAIN" in filename.upper():
            test_filename = filename
            break
        elif test_type == "uk" and "UK" in filename.upper():
            test_filename = filename
            break
        elif test_type == "redd" and "REDD" in filename.upper():
            test_filename = filename
            break
        elif (
            test_type == "test"
            and "TEST" in filename.upper()
            and "TRAIN" not in filename.upper()
            and "UK" not in filename.upper()
        ):
            test_filename = filename
            break
        elif test_type == "val" and "VALIDATION" in filename.upper():
            test_filename = filename
            break
    return test_filename


def load_dataset(file_name, crop=None):
    """Load CSV file and return mains power, appliance power and status."""
    df = pd.read_csv(file_name, nrows=crop)

    mains_power = np.array(df.iloc[:, 0], dtype=np.float32)
    appliance_power = np.array(df.iloc[:, 1], dtype=np.float32)
    activations = np.array(df.iloc[:, 2], dtype=np.float32)

    return mains_power, appliance_power, activations


def get_window_generator(keras_sequence=True):
    """Wrapper to conditionally subclass WindowGenerator as Keras sequence.

    The WindowGenerator is used in keras and non-keras applications and
    so to make it useable across both it can be a subclass of a keras
    sequence. This increases reusability throughout codebase.

    Arguments:
        keras_sequence: If true make WindowGenerator a subclass of
        the keras sequence class.

    Returns:
        WindowGenerator class.
    """
    if keras_sequence:
        from tensorflow import keras

    class WindowGenerator(keras.utils.Sequence if keras_sequence else object):
        """Generates windowed time series samples, targets and status.

        If 'p' is not None the input samples are processed with random masking,
        where a proportion 'p' of input elements are randomly masked with a
        special token and only output results from such positions are used to
        compute the loss using a keras model fit() custom train step. This may be
        useful in training transformers in a masked language model fashion (MLM). See:
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"
        (https://arxiv.org/pdf/1810.04805.pdf).

        Attributes:
            dataset: input samples, targets time series data.
            batch_size: mini batch size used in training model.
            window_length: number of samples in a window of time series data.
            train: if True returns samples and targets else just samples.
            shuffle: if True shuffles dataset initially and every epoch.
            model_arch: sets shape of windowed time samples per model architecture.
            p: proportion of input samples masked with a special token.
        """

        def __init__(
            self,
            dataset,
            batch_size=1024,
            window_length=599,
            train=True,
            shuffle=True,
            p=None,
        ) -> None:
            """Inits WindowGenerator."""

            X, y, activations = dataset
            self.batch_size = batch_size
            self.shuffle = shuffle
            self.window_length = window_length
            self.train = train
            self.p = p

            MASK_TOKEN = -1.0

            # Total number of samples in dataset.
            self.total_samples = X.size

            # Calculate window center index.
            self.window_center = int(0.5 * (window_length - 1))

            # Number of input samples adjusted for windowing.
            # This prevents partial window generation.
            self.num_samples = self.total_samples - window_length

            # Generate indices of adjusted input sample array.
            self.indices = np.arange(self.num_samples)

            self.rng = np.random.default_rng()

            if self.p is not None:
                # Randomly mask input sequence.
                self.samples = []
                self.targets = []
                self.status = []
                for i in range(self.total_samples):
                    prob = self.rng.random()
                    if prob < p:
                        prob = self.rng.random()
                        if prob < 0.8:
                            self.samples.append(MASK_TOKEN)
                        elif prob < 0.9:
                            self.samples.append(self.rng.normal())
                        else:
                            self.samples.append(X[i])

                        self.targets.append(y[i])
                        self.status.append(activations[i])
                    else:
                        self.samples.append(X[i])
                        self.targets.append(MASK_TOKEN)
                        self.status.append(MASK_TOKEN)
            else:
                self.samples, self.targets, self.status = X, y, activations

            # Initial shuffle.
            if self.shuffle:
                self.rng.shuffle(self.indices)

        def on_epoch_end(self) -> None:
            """Shuffle at end of each epoch."""
            if self.shuffle:
                self.rng.shuffle(self.indices)

        def __len__(self) -> int:
            """Returns number batches in an epoch."""
            return int(
                np.ceil(self.num_samples / self.batch_size)
            )  # allow partial batch
            # return self.num_samples // self.batch_size # disallow partial batch

        def __getitem__(self, index) -> np.ndarray:
            """Returns windowed samples and targets."""
            # Row indices for current batch.
            rows = self.indices[index * self.batch_size : (index + 1) * self.batch_size]

            # Create a batch of windowed samples.
            wsam = np.array(
                [self.samples[row : row + self.window_length] for row in rows]
            )

            # Add 'channel' axis for model input convnet.
            wsam = wsam.reshape(-1, self.window_length, 1)

            if self.train:
                # Create batch of window-centered, single point targets and status.
                wtar = np.array(
                    [self.targets[row + self.window_center] for row in rows]
                )
                wsta = np.array([self.status[row + self.window_center] for row in rows])

                return wsam, wtar, wsta
            else:
                # Return only samples if in test mode.
                return wsam

    return WindowGenerator


def tflite_infer(interpreter, provider, num_eval, eval_offset=0, log=print) -> list:
    """Perform inference using a tflite model"""
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    log(f"interpreter input details: {input_details}")
    output_details = interpreter.get_output_details()
    log(f"interpreter output details: {output_details}")
    # Check I/O tensor type.
    input_dtype = input_details[0]["dtype"]
    floating_input = input_dtype == np.float32
    log(f"tflite model floating input: {floating_input}")
    output_dtype = output_details[0]["dtype"]
    floating_output = output_dtype == np.float32
    log(f"tflite model floating output: {floating_output}")
    # Get I/O indices.
    input_index = input_details[0]["index"]
    output_index = output_details[0]["index"]
    # If model has int I/O get quantization information.
    if not floating_input:
        input_quant_params = input_details[0]["quantization_parameters"]
        input_scale = input_quant_params["scales"][0]
        input_zero_point = input_quant_params["zero_points"][0]
    if not floating_output:
        output_quant_params = output_details[0]["quantization_parameters"]
        output_scale = output_quant_params["scales"][0]
        output_zero_point = output_quant_params["zero_points"][0]

    # Calculate num_eval sized indices of contiguous locations in provider.
    # Get number of samples per batch in provider. Since batch should always be
    # set to 1 for inference, this will simply return the total number of samples.
    samples_per_batch = provider.__len__()
    if num_eval - eval_offset > samples_per_batch:
        raise ValueError("Not enough test samples to run evaluation.")
    eval_indices = list(range(samples_per_batch))[eval_offset : num_eval + eval_offset]

    log(f"Running inference on {num_eval} samples...")
    start = time.time()

    def infer(i):
        sample, target, _ = provider.__getitem__(i)
        if not sample.any():
            return 0.0, 0.0  # ignore missing data
        ground_truth = np.squeeze(target)
        if not floating_input:  # convert float to int
            sample = sample / input_scale + input_zero_point
            sample = sample.astype(input_dtype)
        interpreter.set_tensor(input_index, sample)
        interpreter.invoke()  # run inference
        result = interpreter.get_tensor(output_index)
        prediction = np.squeeze(result)
        if not floating_output:  # convert int to float
            prediction = (prediction - output_zero_point) * output_scale
        # print(f'sample index: {i} ground_truth: {ground_truth:.3f} prediction: {prediction:.3f}')
        return ground_truth, prediction

    results = [infer(i) for i in tqdm(eval_indices)]
    end = time.time()
    log("Inference run complete.")
    log(f"Inference rate: {num_eval / (end - start):.3f} Hz")

    return results


def normalize(dataset):
    """Normalize or standardize a dataset."""
    import numpy as np

    # Compute aggregate statistics.
    agg_mean = np.mean(dataset[0])
    agg_std = np.std(dataset[0])
    print(f"agg mean: {agg_mean}, agg std: {agg_std}")
    agg_median = np.percentile(dataset[0], 50)
    agg_quartile1 = np.percentile(dataset[0], 25)
    agg_quartile3 = np.percentile(dataset[0], 75)
    print(f"agg median: {agg_median}, agg q1: {agg_quartile1}, agg q3: {agg_quartile3}")
    # Compute appliance statistics.
    app_mean = np.mean(dataset[1])
    app_std = np.std(dataset[1])
    print(f"app mean: {app_mean}, app std: {app_std}")
    app_median = np.percentile(dataset[1], 50)
    app_quartile1 = np.percentile(dataset[1], 25)
    app_quartile3 = np.percentile(dataset[1], 75)
    print(f"app median: {app_median}, app q1: {app_quartile1}, app q3: {app_quartile3}")

    def z_norm(dataset, mean, std):
        return (dataset - mean) / std

    def robust_scaler(dataset, median, quartile1, quartile3):
        return (dataset - median) / (quartile3 - quartile1)

    return (
        z_norm(dataset[0], agg_mean, agg_std),
        z_norm(dataset[1], app_mean, app_std),
    )


def compute_status(appliance_power: np.ndarray, appliance: str) -> list:
    """Compute appliance on-off status."""
    threshold = params_appliance[appliance]["on_power_threshold"]

    def ceildiv(a: int, b: int) -> int:
        """Upside-down floor division."""
        return -(a // -b)

    # Convert durations from seconds to samples.
    min_on_duration = ceildiv(
        params_appliance[appliance]["min_on_duration"], SAMPLE_PERIOD
    )
    min_off_duration = ceildiv(
        params_appliance[appliance]["min_off_duration"], SAMPLE_PERIOD
    )

    # Apply threshold to appliance powers.
    initial_status = appliance_power.copy() >= threshold

    # Find transistion indices.
    status_diff = np.diff(initial_status)
    events_idx = status_diff.nonzero()
    events_idx = np.array(events_idx).squeeze()
    events_idx += 1

    # Adjustment for first and last transition.
    if initial_status[0]:
        events_idx = np.insert(events_idx, 0, 0)
    if initial_status[-1]:
        events_idx = np.insert(events_idx, events_idx.size, initial_status.size)

    # Separate out on and off events.
    events_idx = events_idx.reshape((-1, 2))
    on_events = events_idx[:, 0].copy()
    off_events = events_idx[:, 1].copy()
    assert len(on_events) == len(off_events)

    # Filter out on and off transitions faster than minimum values.
    if len(on_events) > 0:
        off_duration = on_events[1:] - off_events[:-1]
        off_duration = np.insert(off_duration, 0, 1000)
        on_events = on_events[off_duration > min_off_duration]
        off_events = off_events[np.roll(off_duration, -1) > min_off_duration]

        on_duration = off_events - on_events
        on_events = on_events[on_duration >= min_on_duration]
        off_events = off_events[on_duration >= min_on_duration]
        assert len(on_events) == len(off_events)

    # Generate final status.
    status = [0] * appliance_power.size
    for on, off in zip(on_events, off_events):
        status[on:off] = [1] * (off - on)

    return status
