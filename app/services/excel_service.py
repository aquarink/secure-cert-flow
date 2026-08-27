"""
Excel & CSV Parser Service
Validates and extracts bulk participant data from uploaded spreadsheets.
"""

import io
import re
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd


def normalize_header(header: str) -> str:
    """Normalizes header string to snake_case alphanumeric format"""
    cleaned = str(header).strip().lower()
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned


class ExcelService:
    # Standard alias mappings
    HEADER_ALIASES = {
        "email": ["email", "e_mail", "email_address", "surel"],
        "nama": ["nama", "name", "full_name", "nama_lengkap", "peserta", "participant"],
        "peran": ["peran", "role", "position", "jabatan", "status", "category", "kategori"],
        "judul_paper": ["judul_paper", "paper_title", "title", "judul", "paper", "judul_makalah"],
    }

    def _map_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Maps varying column header aliases into standard internal keys"""
        column_map = {}
        for col in df.columns:
            norm_col = normalize_header(col)
            mapped = False
            for standard_key, aliases in self.HEADER_ALIASES.items():
                if norm_col in aliases:
                    column_map[col] = standard_key
                    mapped = True
                    break
            if not mapped:
                column_map[col] = norm_col
        
        return df.rename(columns=column_map)

    def parse_file(
        self,
        file_bytes: bytes,
        filename: str,
        required_fields: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Parses spreadsheet bytes into participant record dictionaries.
        Returns:
            Tuple of (valid_records_list, error_messages_list)
        """
        errors = []
        try:
            if filename.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
            elif filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
            else:
                return [], ["Format file tidak didukung. Harap gunakan file .xlsx, .xls, atau .csv."]
        except Exception as e:
            return [], [f"Gagal membaca file spreadsheet: {str(e)}"]

        if df.empty:
            return [], ["File spreadsheet kosong tidak memiliki data."]

        # Fill NaNs with empty string
        df = df.fillna("")
        df = self._map_column_names(df)

        # Validate mandatory minimum columns: email, nama, peran
        base_required = ["email", "nama", "peran"]
        all_required = set(base_required)
        if required_fields:
            for rf in required_fields:
                all_required.add(normalize_header(rf))

        missing_cols = [col for col in all_required if col not in df.columns]
        if missing_cols:
            errors.append(
                f"Kolom wajib tidak ditemukan dalam file: {', '.join(missing_cols)}. "
                f"Header yang terbaca di file: {', '.join(df.columns)}"
            )
            return [], errors

        records = []
        for index, row in df.iterrows():
            row_num = index + 2  # 1-indexed plus header row
            email = str(row.get("email", "")).strip()
            name = str(row.get("nama", "")).strip()
            role = str(row.get("peran", "Attendee")).strip()
            paper_title = str(row.get("judul_paper", "")).strip()

            if not email or not name:
                errors.append(f"Baris #{row_num}: Email atau Nama tidak boleh kosong.")
                continue

            # Basic email format validation
            if "@" not in email or "." not in email:
                errors.append(f"Baris #{row_num}: Format email '{email}' tidak valid.")
                continue

            # Extract any other custom dynamic fields
            custom_data = {}
            for col in df.columns:
                if col not in ["email", "nama", "peran", "judul_paper"]:
                    custom_data[col] = str(row.get(col, "")).strip()

            records.append({
                "row_number": row_num,
                "email": email,
                "name": name,
                "role": role,
                "paper_title": paper_title if paper_title else None,
                "custom_data": custom_data,
                "dynamic_values": {
                    "nama": name,
                    "peran": role,
                    "judul_paper": paper_title,
                    "email": email,
                    **custom_data
                }
            })

        return records, errors


# Global Excel Service Singleton
excel_service = ExcelService()
