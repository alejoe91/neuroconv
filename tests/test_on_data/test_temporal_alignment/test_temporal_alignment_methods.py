from tempfile import mkdtemp
from shutil import rmtree
from pathlib import Path

import numpy as np
from numpy.testing import assert_array_equal
from hdmf.testing import TestCase
from pandas import DataFrame

from neuroconv import ConverterPipe
from neuroconv.datainterfaces import CsvTimeIntervalsInterface
from neuroconv.tools.testing import MockBehaviorEventInterface, MockSpikeGLXNIDQInterface


class TestNIDQInterfaceAlignment(TestCase):
    @classmethod
    def setUpClass(cls):
        trial_system_delayed_start = 3.23  # Trial tracking system starts 3.23 seconds after SpikeGLX
        trial_system_total_time = 10.0  # Was tracking trials for 10 seconds, according to trial tracking system
        cls.regular_trial_length = (
            1.0  # For simplicity, each trial lasts 1 second according to the trial tracking system
        )
        trial_system_average_delay_per_second = 0.0001  # Clock on trial tracking system is slightly slower than NIDQ
        # The drift from the trial tracking system adds up over time
        trial_system_delayed_stop = trial_system_average_delay_per_second * trial_system_total_time

        cls.unaligned_trial_start_times = np.arange(
            start=0.0, stop=trial_system_total_time, step=cls.regular_trial_length
        )
        cls.aligned_trial_start_times = np.linspace(  # use linspace to match the exact length of timestamps
            start=trial_system_delayed_start, stop=trial_system_delayed_stop, num=len(cls.unaligned_trial_start_times)
        )

        # Timing of events according to trial system
        cls.unaligned_behavior_event_timestamps = [5.6, 7.3, 9.7]  # Timing of events according to trial tracking system

        # Timing of events when interpolated by aligned trial times
        cls.aligned_behavior_event_timestamps = [8.83168, 10.53219, 12.93291]

        cls.tmpdir = Path(mkdtemp())
        cls.csv_file_path = cls.tmpdir / "testing_nidq_alignment_trial_table.csv"
        dataframe = DataFrame(
            data=dict(
                start_time=cls.unaligned_trial_start_times,
                stop_time=cls.unaligned_trial_start_times + cls.regular_trial_length,
            )
        )
        dataframe.to_csv(path_or_buf=cls.csv_file_path, index=False)

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.tmpdir)

    def setUp(self):
        self.nidq_interface = MockSpikeGLXNIDQInterface(
            signal_duration=23.0, ttl_times=[self.aligned_trial_start_times], ttl_duration=0.01
        )
        self.trial_interface = CsvTimeIntervalsInterface(file_path=self.csv_file_path)
        self.behavior_interface = MockBehaviorEventInterface(event_times=self.unaligned_behavior_event_timestamps)

    def test_alignment_interfaces(self):
        inferred_aligned_trial_start_timestamps = (
            self.nidq_interface.get_event_times_from_ttl(
                channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
            ),
        )

        self.trial_interface.align_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps, column="start_time"
        )

        # True stop times are not tracked, so estimate them from using the known regular trial length
        self.trial_interface.align_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps + self.regular_trial_length, column="stop_time"
        )

        self.behavior_interface.align_by_interpolation(
            aligned_timestamps=inferred_aligned_trial_start_timestamps,
            unaligned_timestamps=self.unaligned_trial_start_times,
        )

        assert_array_equal(
            x=self.trial_interface.get_timestamps(column="start_time"), y=inferred_aligned_trial_start_timestamps
        )
        assert_array_equal(
            x=self.trial_interface.get_timestamps(column="stop_time"), y=inferred_aligned_trial_start_timestamps + 1.0
        )
        assert_array_equal(x=self.behavior_interface.get_timestamps(), y=self.aligned_behavior_event_timestamps)

    def test_alignment_nwbconverter(self):
        pass  # TODO

    def test_alignment_converter_pipe(self):
        inferred_aligned_trial_start_timestamps = (
            self.nidq_interface.get_event_times_from_ttl(
                channel_name="nidq#XA0"  # The channel receiving pulses from the DLC system
            ),
        )

        self.trial_interface.align_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps, column="start_time"
        )

        # True stop times are not tracked, so estimate them from using the known regular trial length
        self.trial_interface.align_timestamps(
            aligned_timestamps=inferred_aligned_trial_start_timestamps + self.regular_trial_length, column="stop_time"
        )

        self.behavior_interface.align_by_interpolation(
            aligned_timestamps=inferred_aligned_trial_start_timestamps,
            unaligned_timestamps=self.unaligned_trial_start_times,
        )

        converter = ConverterPipe(
            [self.spikeglx_interface, self.dlc_interface, self.nidq_interface, self.behavior_interface]
        )
        metadata = converter.get_metadata()
        converter.run_conversion(metadata=metadata)

        # TODO, test round-trip output in a written nwbfile


class TestExternalAlignment(TestNIDQInterfaceAlignment):
    """
    This test case is less about ensuring the functionality (which is identical to above) and more about depicting
    the intended usage in practice.
    """

    def setUp(self):
        self.trial_interface = CsvTimeIntervalsInterface(file_path=self.csv_file_path)
        self.behavior_interface = MockBehaviorEventInterface()

    def test_alignment_interfaces(self):
        """
        Some labs already have workflows put together for handling synchronization.

        In this case, they simply store the timestamps in separate files and load them in during the conversion.
        """
        externally_aligned_timestamps = self.aligned_trial_start_times

        self.trial_interface.align_timestamps(aligned_timestamps=externally_aligned_timestamps, column="start_time")

        # True stop times are not tracked, so estimate them from using the known regular trial length
        self.trial_interface.align_timestamps(
            aligned_timestamps=externally_aligned_timestamps + self.regular_trial_length, column="stop_time"
        )

        self.behavior_interface.align_by_interpolation(
            aligned_timestamps=externally_aligned_timestamps,
            unaligned_timestamps=self.unaligned_trial_start_times,
        )

        assert_array_equal(x=self.trial_interface.get_timestamps(column="start_time"), y=externally_aligned_timestamps)
        assert_array_equal(
            x=self.trial_interface.get_timestamps(column="stop_time"), y=externally_aligned_timestamps + 1.0
        )
        assert_array_equal(x=self.behavior_interface.get_timestamps(), y=self.aligned_behavior_event_timestamps)

    def test_alignment_nwbconverter(self):
        pass  # TODO

    def test_alignment_converter_pipe(self):
        """
        Some labs already have workflows put together for handling synchronization.

        In this case, they simply store the timestamps in separate files and load them in during the conversion.
        """
        externally_aligned_timestamps = self.aligned_trial_start_times

        self.trial_interface.align_timestamps(aligned_timestamps=externally_aligned_timestamps, column="start_time")

        # True stop times are not tracked, so estimate them from using the known regular trial length
        self.trial_interface.align_timestamps(
            aligned_timestamps=externally_aligned_timestamps + self.regular_trial_length, column="stop_time"
        )

        self.behavior_interface.align_by_interpolation(
            aligned_timestamps=externally_aligned_timestamps,
            unaligned_timestamps=self.unaligned_trial_start_times,
        )

        converter = ConverterPipe(
            [self.spikeglx_interface, self.dlc_interface, self.nidq_interface, self.behavior_interface]
        )
        metadata = converter.get_metadata()
        converter.run_conversion(metadata=metadata)

        # TODO, test round-trip output in a written nwbfile
