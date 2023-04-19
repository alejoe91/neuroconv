import numpy as np
from dateutil.parser import parse

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FolderPathType


class BrukerTiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for BrukerTiffImagingExtractor."""

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The path that points to the folder containing the Bruker TIF image files and configuration files."
        return source_schema

    def __init__(self, folder_path: FolderPathType, verbose: bool = True):
        """
        Initialize reading of TIFF files.

        Parameters
        ----------
        folder_path : FolderPathType
            The path to the folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env).
        verbose : bool, default: True
        """
        super().__init__(folder_path=folder_path, verbose=verbose)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        xml_metadata = self.imaging_extractor.xml_metadata
        session_start_time = parse(xml_metadata["date"])
        metadata["NWBFile"].update(session_start_time=session_start_time)

        description = f"Version {xml_metadata['version']}"
        device_name = "Bruker Fluorescence Microscope"
        metadata["Ophys"]["Device"][0].update(
            name=device_name,
            description=description,
        )

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]

        microns_per_pixel = xml_metadata["micronsPerPixel"]
        if microns_per_pixel:
            image_size = self.imaging_extractor.get_image_size()
            x_position_in_meters = float(microns_per_pixel[0]["XAxis"]) / 1e6
            y_position_in_meters = float(microns_per_pixel[1]["YAxis"]) / 1e6
            z_plane_position_in_meters = float(microns_per_pixel[2]["ZAxis"]) / 1e6
            grid_spacing = np.array([x_position_in_meters, y_position_in_meters]) / image_size
            imaging_plane_metadata.update(
                grid_spacing=grid_spacing, description=f"The plane imaged at {z_plane_position_in_meters} meters depth."
            )

        imaging_plane_metadata.update(
            device=device_name,
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )

        return metadata
