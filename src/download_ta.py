
import os
import urllib.request

BASE = "https://assets.publishing.service.gov.uk/media/"
FILES = {
    "2019_Q3": "5ec53218e90e0754d1dedf18/DetailedLA_201909_revised.xlsx",
    "2019_Q4": "5f749aaad3bf7f2868b3ffa2/DetailedLA_201912_revised.ods",
    "2020_Q1": "65e6e8207bc329020bb8c266/Detailed_LA_202003_Revised_Fixed.ods",
    "2020_Q2": "65e6e8372f2b3be8b07cd78e/Detailed_LA_202006_Revised_Fixed.ods",
    "2020_Q3": "60803c88e90e076aab2a0531/DetailedLA_202009_Revised.ods",
    "2020_Q4": "60fae728d3bf7f04599e2170/DetailedLA_202012_Revised_updated.ods",
    "2021_Q1": "61796748e90e0719833464ff/DetailedLA_202103_Revised.ods",
    "2021_Q2": "6a2c204ce50716856ed4b00e/DetailedLA_202106_revised_corrected.ods",
    "2021_Q3": "62694963d3bf7f0e7121ae4b/DetailedLA_202109_revised.ods",
    "2021_Q4": "62e14c208fa8f564a21dcd8a/Detailed_LA_202112_revised.ods",
    "2022_Q1": "637e39e0d3bf7f153b8b321c/Detailed_LA_202203_revised.ods",
    "2022_Q2": "6400d30c8fa8f527ff6b42db/Detailed_LA_202206_revised_Updated.ods",
    "2022_Q3": "645a5900479612000cc29274/V2_Detailed_LA_202209_revised.ods",
    "2022_Q4": "64be88f41e10bf000e17cd3a/Detailed_LA_202212_revised.ods",
    "2023_Q1": "65804b3f83ba38000de1b77a/Detailed_LA_202303_Revised.ods",
    "2023_Q2": "65df3f24cf7eb16adff57f55/Detailed_LA_202306_revised.ods",
    "2023_Q3": "662f6dd89e82181baa98a8f5/Detailed_LA_202309_revised.ods",
    "2023_Q4": "66b331c5a3c2a28abb50ddfd/Detailed_LA_202312_Revised_No_Dropdowns.ods",
    "2024_Q1": "6747279da72d7eb7f348c04c/Detailed_LA_202403.xlsx",
    "2024_Q2": "699d950a532c9ad91ebbcbd2/Statutory_Homelessness_Detailed_Local_Authority_Data_202406_revised.ods",
    "2024_Q3": "699d953607d7bff3604d6c0a/Statutory_Homelessness_Detailed_Local_Authority_Data_202409_revised.ods",
    "2024_Q4": "699d956edb2401de164d6c1c/Statutory_Homelessness_Detailed_Local_Authority_Data_202412_revised.ods",
    "2025_Q1": "699d95ae07d7bff3604d6c0c/Statutory_Homelessness_Detailed_Local_Authority_Data_202503_revised.ods",
    "2025_Q2": "6a2c1fe0e50716856ed4b008/Detailed_LA_202506_revised_corrected.xlsx",
    "2025_Q3": "69f089bd606c20d4121634b7/Statutory_Homelessness_Detailed_Local_Authority_Data_202509_revised.ods",
    "2025_Q4": "6a8302c63be22055c1aaa3c2/Statutory_Homelessness_Detailed_Local_Authority_Data_202512_revised.ods",
    "2026_Q1": "6a82eeb83bd75b81e2329a7a/Statutory_Homelessness_Detailed_Local_Authority_Data_202603.ods",
}

os.makedirs("data/raw", exist_ok=True)
for quarter, path in FILES.items():
    ext = os.path.splitext(path)[1]
    dest = f"data/raw/ta_{quarter}{ext}"
    if os.path.exists(dest):
        print(f"already have {dest}")
        continue
    print(f"downloading {dest} ...", end=" ", flush=True)
    try:
        req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            f.write(r.read())
        print("done")
    except Exception as e:
        print(f"FAILED ({e}). Download by hand: {BASE + path}")
print("\nFinished. Next: python3 src/clean_ta.py data/raw/ta_*")