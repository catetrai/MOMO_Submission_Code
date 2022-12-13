import csv
import sys
import argparse
from pathlib import Path
from textwrap import dedent

from MOMO_Backbone import (
    GatherSeriesMetadataFromStudy,
    PredictSeriesWithNetwork,
    from_config,
    meta
)
# Hardcoded imports of the network classes the paper uses for MOMO (Pickle needs these available in the top level namespace)
from ipynb.fs.defs.TransferRes import *
from ipynb.fs.defs.TransferDense import *


def predict_series(series_path, verbose=True) -> dict:
    """Path: directory of chosen DICOM series"""

    # Load config ini file
    configfile = "./default_config.ini"
    (
        config_mapfile,
        config_network,
        config_networkscript,
        config_known_metas,
        config_verbose,
        config_local,
        config_split_mode,
        config_kwargs,
    ) = from_config(configfile)

    meta_dict, file_names, series_ids = GatherSeriesMetadataFromStudy(
        data_root=series_path, known_metas=config_known_metas, verbose=verbose
    )
    assert len(file_names) == 1
    assert len(series_ids) == 1

    # Get SeriesInstanceUID (should be included in 'known_metas' section of config file)
    #series_instance_uid = meta_dict["Series Instance UID"][0]
    #assert series_instance_uid is not None

    # Do not care about Study Description or Series Description
    STDesc = "dummy"
    SEDesc = "dummy"

    # Series and Study Modality should always be MR
    SEModas = [item for item in meta_dict["Series Modality"]]
    assert len(SEModas) == 1
    assert SEModas[0].value == "MR"
    STModa = SEModas[0].value

    # If split mode, figure out network/mapfile, then predict, else predict with default network/mapfile
    mapfile = config_kwargs["mapfiles"][STModa]
    network = config_kwargs["networks"][STModa]

    # Do prediction
    eligibility, probability, prediction = PredictSeriesWithNetwork(
        STModa=STModa,
        SEDesc=SEDesc,
        SEModa=STModa,
        SEFN=file_names[0],
        SEID=series_ids[0],
        mapfile=mapfile,
        network=network,
        verbose=verbose,
        **config_kwargs
    )

    return {
        "series_instance_uid": series_ids[0],
        "dir_path": series_path,
        "eligibility": eligibility,
        "prediction": prediction,
        "probability": probability
    }


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(
            """
            Predict body part for MRI series under a given directory
            and write results to a CSV file.
            """
        ),
    )
    parser.add_argument(
        "patient_dirs",
        nargs="+",
        help="One or more paths to patient-level DICOM directories",
    )
    parser.add_argument(
        "csv_file",
        type=argparse.FileType("w", encoding="utf-8"),
        help="Output CSV file to be written",
    )
    args = parser.parse_args()

    writer = csv.DictWriter(args.csv_file, fieldnames=columns)
    writer.writeheader()
    columns = ["series_instance_uid", "dir_path", "eligibility", "prediction", "probability"]

    for patient_dir in args.patient_dirs:
        all_series = (d for d in Path(patient_dir).glob("*/*") if d.is_dir())

        for series_dir in all_series:
            print(series_dir)
            results = {}
            try:
                results = predict_series(str(series_dir), verbose=False)
                print(results)
                writer.writerow(results)
            except Exception as ex:
                print(f"ERROR: {ex}")


if __name__ == "__main__":
    main()

