# DICOM Renamer/Anonymiser

DICOM anonymiser that can also function as a DICOM renamer

Usage:
So far this is a console app, GUI version to come soon

`python dicom_anon_console.py -i path/to/input_dicom -o (optional) path/to/dicom_anon`

Parameters:
- -i/-input: relative path to directory of DICOM files (.dcm only, DICOMDIR not supported yet)
- -o/-output: relative path to output directory

tags.ini:
- This is the config file of all the optional tags to be removed
- Will be created automatically if not found in the same directory as the python file

Syntax:

`[TAGS_TO_REMOVE]
patient birth date = (0x0010, 0x0030)
tag_name (not actually used, for human understanding only) = (0xtag, 0xtag)
`

## Requirements
Pydicom

## Default tags to be altered
Tags that will always be altered:
- Name      [0x0010, 0x0010] - Replaced with a hash of the ID
- ID        [0x0010, 0x0020] - Replaced with a hash of the ID
- Accession [0x0008, 0x0050] - Kept for now

Tags to be removed (customisable):
- Patient Birth Date        [0x0010, 0x0030]
- Referrer                  [0x0008, 0x0090]
- Patient Address           [0x0010, 0x1040]
- Patient Weight            [0x0010, 0x1030]
- Patient Age               [0x0010, 0x1010]
- Patient Sex               [0x0010, 0x0040]
- Medical Alerts            [0x0010, 0x2000]
- Issuer of Patient ID      [0x0008, 0x0021]
- Study Date                [0x0008, 0x0020]
- Study Time                [0x0008, 0x0030]
- Station Name              [0x0008, 0x1010]
- Operator Name             [0x0008, 0x1070]
- Institution Address       [0x0008, 0x0081]
- Institution Name          [0x0008, 0x0080]
- Referrer Address          [0x0008, 0x0092]
- Referrer Telephone        [0x0008, 0x0094]
- Physicians of Record      [0x0008, 0x1048]
- Performing Physician      [0x0008, 0x1050]
- Referring Physician Name  [0x0008, 0x1050]\

## TODO
- GUI version
- DICOMDIR support
- Change behaviour of name/ic/accession