from typing import Optional
from warnings import warn

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....utils import FolderPathType, get_schema_from_method_signature


class OpenEphysBinaryRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface for converting binary OpenEphys data (.dat files). Uses
    :py:class:`~spikeinterface.extractors.OpenEphysBinaryRecordingExtractor`."""

    ExtractorName = "OpenEphysBinaryRecordingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        """Compile input schema for the RecordingExtractor."""
        source_schema = get_schema_from_method_signature(
            method=cls.__init__, exclude=["recording_id", "experiment_id", "stub_test"]
        )
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to directory containing OpenEphys binary files."
        return source_schema

    def __init__(
        self,
        folder_path: FolderPathType,
        stub_test: bool = False,
        verbose: bool = True,
        es_key: str = "ElectricalSeries",
    ):
        """
        Initialize reading of OpenEphys binary recording.

        Parameters
        ----------
        folder_path: FolderPathType
            Path to OpenEphys directory.
        stub_test : bool, default: False
        verbose : bool, default: True
        es_key : str, default: "ElectricalSeries"
        """

        from spikeinterface.extractors import OpenEphysBinaryRecordingExtractor

        self.RX = OpenEphysBinaryRecordingExtractor
        super().__init__(folder_path=folder_path, verbose=verbose, es_key=es_key)

        if stub_test:
            self.subset_channels = [0, 1]

    def get_metadata(self) -> dict:
        """Auto-fill as much of the metadata as possible. Must comply with metadata schema."""
        import pyopenephys

        metadata = super().get_metadata()

        folder_path = self.source_data["folder_path"]
        fileobj = pyopenephys.File(foldername=folder_path)
        session_start_time = fileobj.experiments[0].datetime

        metadata["NWBFile"].update(session_start_time=session_start_time)
        return metadata


class OpenEphysSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting OpenEphys spiking data."""

    @classmethod
    def get_source_schema(cls) -> dict:
        """Compile input schema for the SortingExtractor."""
        metadata_schema = get_schema_from_method_signature(
            method=cls.__init__, exclude=["recording_id", "experiment_id"]
        )
        metadata_schema["properties"]["folder_path"].update(description="Path to directory containing OpenEphys files.")
        metadata_schema["additionalProperties"] = False
        return metadata_schema

    def __init__(self, folder_path: FolderPathType, experiment_id: int = 0, recording_id: int = 0):
        from spikeextractors import OpenEphysSortingExtractor

        self.Extractor = OpenEphysSortingExtractor
        super().__init__(folder_path=str(folder_path), experiment_id=experiment_id, recording_id=recording_id)
