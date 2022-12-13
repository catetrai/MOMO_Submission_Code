import csv
import json
import sys
import logging
import argparse
from pathlib import Path
from textwrap import dedent

from MOMO_Backbone import (
    GatherSeriesMetadataFromStudy,
    PredictSeriesWithNetwork,
    from_config,
    meta
)
import SimpleITK as sitk

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

    body_part_codes = {
        "MRS": "HEAD",
        "MRSH": "HEADNECK",
        "MRA": "ABDOMEN",
        "MRB": "TSPINE",
        "MRBE": "PELVIS",
        "MRH": "CSPINE",
        "MRL": "LSPINE",
        "MRM": "BREAST",
        "MROE": "UPPER_EXT",
        "MRTH": "CHEST",
        "MRUE": "LOWER_EXT",
        "MRWB": "WHOLE_BODY",
        "MRWS": "SPINE",
    }

    return {
        "series_instance_uid": series_ids[0],
        "dir_path": series_path,
        "eligibility": eligibility,
        "prediction": body_part_codes.get(prediction),
        "probability": probability
    }


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(
            """
            Predict body part for MRI series under a given directory
            and optionally write results to a CSV file.
            """
        ),
    )
    path_args_group = parser.add_mutually_exclusive_group(required=True)
    path_args_group.add_argument(
        "--study-dirs",
        nargs="+",
        help="One or more directory paths containing DICOM series directories",
    )
    path_args_group.add_argument(
        "--series-dirs",
        nargs="+",
        help="One or more DICOM series directory paths containing DICOM image files",
    )
    parser.add_argument(
        "--csv-file",
        type=argparse.FileType("w", encoding="utf-8"),
        help="Optional CSV file where results will be written (by default, writes to stdout)",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Disable log output"
    )
    args = parser.parse_args()


    if args.debug:
        logging.basicConfig(format="%(asctime)s [%(levelname)-8s] %(message)s",
                            level=logging.DEBUG)
    if args.quiet:
        logging.getLogger().disabled = True
        # Disable SimpleITK warnings when reading images
        sitk.ProcessObject_SetGlobalWarningDisplay(False)


    columns = ["series_instance_uid", "dir_path", "eligibility", "prediction", "probability"]
    if args.csv_file:
        writer = csv.DictWriter(args.csv_file, fieldnames=columns)
        writer.writeheader()

    if args.study_dirs:
        all_series = (d for study_dir in args.study_dirs for d in Path(study_dir).iterdir() if d.is_dir())
    elif args.series_dirs:
        all_series = args.series_dirs
    else:
        raise ValueError("Must specify either '--study-dirs' or '--series-dirs'")
        

    results_all = []
    for series_dir in all_series:
        logging.debug("Predicting series '%s'", series_dir)
        results = {}

        try:
            results = predict_series(str(series_dir), verbose=False)
            results_all.append(results)

            if args.csv_file:
                writer.writerow(results)

        except Exception as ex:
            logging.error("Error predicting series '%s'", series_dir)
            logging.exception(ex)

    print(json.dumps(results_all))


if __name__ == "__main__":
    main()

