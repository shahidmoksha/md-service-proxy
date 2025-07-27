"""
Utility functions for image manipulation
"""

import math
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from pydicom.valuerep import PersonName
from logger import logger
from config import ANNOTATION_COLOR


def burn_metadata_on_jpeg(jpeg_path: Path, metadata: dict, output_path: Path = None):
    """
    Function to addd study metadata in the four corners of the given JPEG file
    """
    image = Image.open(jpeg_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size

    # Font size is 1.7% of image height or 10, whichever is less
    font_size = calculate_font_size(height)

    # Padding is 50% of font size
    padding = math.ceil(font_size * 0.5)

    # Line spacing is 25% of font size
    line_spacing = font_size + math.ceil(font_size * 0.25)

    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception as e:
        logger.warning("Arial font not found! %s", e)
        font = ImageFont.load_default()

    # Top-left
    tl_lines = [
        f"Name: {format_person_name(metadata.get('PatientName', ''))}",
        f"ID: {metadata.get('PatientID', '')}",
        f"Date: {format_study_date(metadata.get('StudyDate', ''))}",
    ]
    y_tl = padding
    for line in tl_lines:
        draw.text((padding, y_tl), line, fill=ANNOTATION_COLOR, font=font)
        y_tl += line_spacing

    # Top-right
    tr_lines = [
        f"Series: {metadata.get('SeriesNumber', '')}",
        f"Image: {metadata.get('InstanceNumber', '')}",
    ]
    y_tr = padding
    for line in tr_lines:
        text_width = draw.textlength(line, font=font)
        draw.text(
            (width - text_width - padding, y_tr), line, fill=ANNOTATION_COLOR, font=font
        )
        y_tr += line_spacing

    # Bottom-left
    bl_lines = [
        f"Modality: {metadata.get('Modality', '')}",
        f"Study: {metadata.get('StudyDescription', '')} / {metadata.get('BodyPartExamined', '')}",
    ]
    y_bl = height - (len(bl_lines) * line_spacing) - padding
    for line in bl_lines:
        draw.text((padding, y_bl), line, fill=ANNOTATION_COLOR, font=font)
        y_bl += line_spacing

    # Bottom-right
    br_lines = [
        f"{metadata.get('InstitutionName', '')}",
        f"{format_person_name(metadata.get('ReferringPhysicianName', ''))}",
    ]
    y_br = height - (len(br_lines) * line_spacing) - padding
    for line in br_lines:
        text_width = draw.textlength(line, font=font)
        draw.text(
            (width - text_width - padding, y_br), line, fill=ANNOTATION_COLOR, font=font
        )
        y_br += line_spacing

    # Save annotated image
    output_path = output_path or jpeg_path
    image.save(output_path)


def calculate_font_size(image_height):
    """
    Function to calculate the font size based on height of the image.
    Calculates 1.7% of image height or 10, whichever is less.
    Returns the calculated font size.
    """
    if not image_height:
        return 9
    calc_font_size = math.ceil(image_height * 0.017)
    if calc_font_size < 9:
        return 9
    logger.debug("Calculated Font Size: %d", calc_font_size)
    return calc_font_size


def format_person_name(name_raw):
    """
    Function to render DICOM Person Name in human readable format.
    Returns formatted name.
    """
    if not name_raw:
        return ""
    name = PersonName(name_raw)
    return " ".join(
        part for part in [name.given_name, name.middle_name, name.family_name] if part
    )


def format_study_date(date_str):
    """
    Function to render DICOM Study Date in human readable format.
    Return formatted name.
    """
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        return dt.strftime("%d-%b-%Y")
    except ValueError:
        return date_str  # fallback to raw
