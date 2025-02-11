# -*- coding: utf-8 -*-
from tifffile import imread
import pandas as pd
from skimage import measure
import numpy as np
import cv2 as cv
from nmco.nuclear_features import (
    Boundary_global as BG,
    Img_texture as IT,
    Int_dist_features as IDF,
    Boundary_local_curvature as BLC,
)
from tqdm.notebook import tqdm


def run_nuclear_chromatin_feat_ext(raw_image_path, labelled_image_path, output_dir):
    """
    Function that reads in the raw and segmented/labelled images for a field of view and computes nuclear features. 
    Note this has been used only for DAPI stained images
    Args:
        raw_image_path: path pointing to the raw image
        labelled_image_path: path pointing to the segmented image
        output_dir: path where the results need to be stored
    """
    labelled_image = imread(labelled_image_path)
    raw_image = imread(raw_image_path)
    labelled_image = labelled_image.astype(int)
    raw_image = raw_image.astype(int)

    # Insert code for preprocessing image
    # Eg normalize
    # raw_image = cv.normalize(
    #      raw_image, None, alpha=0, beta=255, norm_type=cv.NORM_MINMAX, dtype=cv.CV_32F
    #  )
    # raw_image[raw_image < 0] = 0.0
    # raw_image[raw_image > 255] = 255.0

    # Get features for the individual nuclei in the image
    props = measure.regionprops(labelled_image, raw_image)

    # Measure scikit's built in features
    propstable = measure.regionprops_table(
        labelled_image,
        raw_image,
        cache=True,
        properties=[
            "label",
            "area",
            "perimeter",
            "bbox",
            "bbox_area",
            "convex_area",
            "equivalent_diameter",
            "major_axis_length",
            "minor_axis_length",
            "eccentricity",
            "orientation",
            "centroid",
            "weighted_centroid",
            "weighted_moments",
            "weighted_moments_normalized",
            "weighted_moments_central",
            "weighted_moments_hu",
            "moments",
            "moments_normalized",
            "moments_central",
            "moments_hu",
        ],
    )
    propstable = pd.DataFrame(propstable)

    # measure other inhouse features
    all_features = pd.concat(
        [
            BLC.curvature_features(props[0].image, step=5).reset_index(drop=True),
            BG.boundary_features(
                props[0].image, centroids=props[0].local_centroid
            ).reset_index(drop=True),
            IDF.intensity_features(
                props[0].image, props[0].intensity_image
            ).reset_index(drop=True),
            IT.texture_features(props[0].image, props[0].intensity_image),
            pd.DataFrame([1], columns=["label"]),
        ],
        axis=1,
    )
    for i in tqdm(range(1, len(props))):
        all_features = all_features.append(
            pd.concat(
                [
                    BLC.curvature_features(props[i].image, step=5).reset_index(
                        drop=True
                    ),
                    BG.boundary_features(
                        props[i].image, centroids=props[i].local_centroid
                    ).reset_index(drop=True),
                    IDF.intensity_features(
                        props[i].image, props[i].intensity_image
                    ).reset_index(drop=True),
                    IT.texture_features(props[i].image, props[i].intensity_image),
                    pd.DataFrame([i + 1], columns=["label"]),
                ],
                axis=1,
            ),
            ignore_index=True,
        )

    # Add in other related features for good measure
    features = pd.merge(all_features, propstable, on="label")
    features["concavity"] = (features["convex_area"] - features["area"]) / features[
        "convex_area"
    ]
    features["solidity"] = features["area"] / features["convex_area"]
    features["a_r"] = features["minor_axis_length"] / features["major_axis_length"]
    features["shape_factor"] = (features["perimeter"] ** 2) / (
        4 * np.pi * features["area"]
    )
    features["area_bbarea"] = features["area"] / features["bbox_area"]
    features["center_mismatch"] = np.sqrt(
        (features["weighted_centroid-0"] - features["centroid-0"]) ** 2
        + (features["weighted_centroid-1"] - features["centroid-1"]) ** 2
    )
    features["smallest_largest_calliper"] = (
        features["min_calliper"] / features["max_calliper"]
    )
    features["frac_peri_w_posi_curvature"] = (
        features["len_posi_curvature"] / features["perimeter"]
    )
    features["frac_peri_w_neg_curvature"] = (
        features["len_neg_curvature"].replace(to_replace="NA", value=0)
        / features["perimeter"]
    )
    features["frac_peri_w_polarity_changes"] = (
        features["npolarity_changes"] / features["perimeter"]
    )

    #save the output
    features.to_csv(output_dir+"/"+labelled_image_path.rsplit('/', 1)[-1][:-4]+".csv")

    return features
