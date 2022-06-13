"""Authors: Cody Baker, Alessio Buccino."""
import sys
from pathlib import Path
from importlib import import_module
from itertools import chain
from jsonschema import validate, RefResolver
from typing import Optional

import click
from dandi.organize import create_unique_filenames_from_metadata
from dandi.metadata import _get_pynwb_metadata

from ...nwbconverter import NWBConverter
from ...utils import dict_deep_update, load_dict_from_file, FilePathType, OptionalFolderPathType


@click.command()
@click.argument("specification-file-path")
@click.option(
    "--data-folder",
    help="Modules to import prior to reading the file(s).",
    type=click.Path(writable=True),
)
@click.option(
    "--output-folder",
    default=None,
    help="Save path for the report file.",
    type=click.Path(writable=True),
)
@click.option("--overwrite", help="Overwrite an existing report file at the location.", is_flag=True)
def run_conversion_from_yaml_cli(
    specification_file_path: str,
    data_folder: Optional[str] = None,
    output_folder: Optional[str] = None,
    overwrite: bool = False,
):
    """
    Run the tool function 'run_conversion_from_yaml' via the command line.

    specification-file-path :
    Path to the .yml specification file.
    """
    run_conversion_from_yaml(
        specification_file_path=specification_file_path,
        data_folder=data_folder,
        output_folder=output_folder,
        overwrite=overwrite,
    )


def run_conversion_from_yaml(
    specification_file_path: FilePathType,
    data_folder: OptionalFolderPathType = None,
    output_folder: OptionalFolderPathType = None,
    overwrite: bool = False,
):
    """
    Run conversion to NWB given a yaml specification file.

    Parameters
    ----------
    specification_file_path : FilePathType
        File path leading to .yml specification file for NWB conversion.
    data_folder : FolderPathType, optional
        Folder path leading to root location of the data files.
        The default is the parent directory of the specification_file_path.
    output_folder : FolderPathType, optional
        Folder path leading to the desired output location of the .nwb files.
        The default is the parent directory of the specification_file_path.
    overwrite : bool, optional
        If True, replaces any existing NWBFile at the nwbfile_path location, if save_to_file is True.
        If False, appends the existing NWBFile at the nwbfile_path location, if save_to_file is True.
        The default is False.
    """
    if data_folder is None:
        data_folder = Path(specification_file_path).parent
    if output_folder is None:
        output_folder = Path(specification_file_path).parent
    else:
        output_folder = Path(output_folder)
    specification = load_dict_from_file(file_path=specification_file_path)
    schema_folder = Path(__file__).parent.parent.parent / "schemas"
    specification_schema = load_dict_from_file(file_path=schema_folder / "yaml_conversion_specification_schema.json")
    sys_uri_base = "file://"
    if sys.platform.startswith("win32"):
        sys_uri_base = "file:/"
    validate(
        instance=specification,
        schema=specification_schema,
        resolver=RefResolver(base_uri=sys_uri_base + str(schema_folder) + "/", referrer=specification_schema),
    )

    global_metadata = specification.get("metadata", dict())
    global_data_interfaces = specification.get("data_interfaces")
    nwb_conversion_tools = import_module(
        name=".",
        package="nwb_conversion_tools",  # relative import, but named and referenced as if it were absolute
    )
    file_counter = 0
    for experiment in specification["experiments"].values():
        experiment_metadata = experiment.get("metadata", dict())
        experiment_data_interfaces = experiment.get("data_interfaces")
        for session in experiment["sessions"]:
            file_counter += 1
            session_data_interfaces = session.get("data_interfaces")
            data_interface_classes = dict()
            data_interfaces_names_chain = chain(
                *[
                    data_interfaces
                    for data_interfaces in [global_data_interfaces, experiment_data_interfaces, session_data_interfaces]
                    if data_interfaces is not None
                ]
            )
            for data_interface_name in data_interfaces_names_chain:
                data_interface_classes.update({data_interface_name: getattr(nwb_conversion_tools, data_interface_name)})
            CustomNWBConverter = type(
                "CustomNWBConverter", (NWBConverter,), dict(data_interface_classes=data_interface_classes)
            )

            source_data = session["source_data"]
            for interface_name, interface_source_data in session["source_data"].items():
                for key, value in interface_source_data.items():
                    source_data[interface_name].update({key: str(Path(data_folder) / value)})
            converter = CustomNWBConverter(source_data=source_data)
            metadata = converter.get_metadata()
            for metadata_source in [global_metadata, experiment_metadata, session.get("metadata", dict())]:
                metadata = dict_deep_update(metadata, metadata_source)
            nwbfile_name = session.get("nwbfile_name", f"temp_nwbfile_name_{file_counter}").strip(".nwb")
            converter.run_conversion(
                nwbfile_path=output_folder / f"{nwbfile_name}.nwb",
                metadata=metadata,
                overwrite=overwrite,
                conversion_options=session.get("conversion_options", dict()),
            )
    # To properly mimic a true dandi organization, the full directory must be populated with NWBFiles.
    all_nwbfile_paths = [nwbfile_path for nwbfile_path in output_folder.iterdir() if nwbfile_path.suffix == ".nwb"]
    if any(["temp_nwbfile_name_" in nwbfile_path.stem for nwbfile_path in all_nwbfile_paths]):
        dandi_metadata_list = []
        for nwbfile_path in all_nwbfile_paths:
            dandi_metadata = _get_pynwb_metadata(path=nwbfile_path)
            dandi_metadata.update(path=nwbfile_path)
            dandi_metadata_list.append(dandi_metadata)
        named_dandi_metadata_list = create_unique_filenames_from_metadata(metadata=dandi_metadata_list)

        for named_dandi_metadata in named_dandi_metadata_list:
            if "temp_nwbfile_name_" in named_dandi_metadata["path"].stem:
                dandi_filename = named_dandi_metadata["dandi_filename"].replace(" ", "_")
                assert (
                    dandi_filename != ".nwb"
                ), f"Not enough metadata available to assign name to {str(named_dandi_metadata['path'])}!"
                named_dandi_metadata["path"].rename(str(output_folder / dandi_filename))


if __name__ == "__main__":
    run_conversion_from_yaml_cli()
