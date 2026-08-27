"""
High-Resolution Certificate Image Rendering Engine
Uses Pillow and QRCode to generate cryptographically-hashed, tamper-proof certificates.
"""

import io
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import qrcode
from app.config import settings

logger = logging.getLogger(__name__)


class CertificateGenerator:
    def __init__(self):
        self.default_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    def _get_font(self, font_name: str, size: int) -> ImageFont.ImageFont:
        """Attempts to load specified TrueType font, falling back gracefully"""
        if not font_name:
            font_name = "Roboto-Bold.ttf"
            
        if not font_name.endswith(".ttf") and not font_name.endswith(".otf"):
            font_name = f"{font_name}.ttf"

        candidate_paths = [
            f"/var/www/sertifikat/static/fonts/{font_name}",
            f"/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/{font_name}",
            f"/usr/share/fonts/truetype/liberation/{font_name}",
            f"/usr/share/fonts/truetype/dejavu/{font_name}",
            f"/usr/share/fonts/truetype/croscore/{font_name}",
            f"/usr/share/fonts/truetype/roboto/{font_name}",
            "/var/www/sertifikat/static/fonts/Cinzel-Bold.ttf",
            "/var/www/sertifikat/static/fonts/Montserrat-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
            "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf",
            self.default_font_path,
        ]
        
        for path in candidate_paths:
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
        
        # Absolute fallback to PIL default font
        return ImageFont.load_default()

    def generate_qr_code(self, data: str, size: int = 150) -> Image.Image:
        """Generates a high-contrast QR Code with clean margin"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        return img_qr.resize((size, size), Image.Resampling.LANCZOS)

    def _smart_wrap_text(
        self,
        text: str,
        font: ImageFont.ImageFont,
        draw: ImageDraw.ImageDraw,
        max_width: int
    ) -> List[str]:
        """
        Wraps text preserving atomic author names and whole words without hyphenation.
        """
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            return [text]

        # 1. If text has author separators ' - ', break by full author items
        if " - " in text:
            authors = text.split(" - ")
            lines = []
            current_line = []
            for a in authors:
                test_line = " - ".join(current_line + [a])
                test_bbox = draw.textbbox((0, 0), test_line, font=font)
                if (test_bbox[2] - test_bbox[0]) <= max_width or not current_line:
                    current_line.append(a)
                else:
                    lines.append(" - ".join(current_line))
                    current_line = [a]
            if current_line:
                lines.append(" - ".join(current_line))
            return lines

        # 2. Standard word-based wrapping without cutting words
        words = text.split(" ")
        lines = []
        current_line = []
        for w in words:
            if not w:
                continue
            test_line = " ".join(current_line + [w])
            test_bbox = draw.textbbox((0, 0), test_line, font=font)
            if (test_bbox[2] - test_bbox[0]) <= max_width or not current_line:
                current_line.append(w)
            else:
                lines.append(" ".join(current_line))
                current_line = [w]
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    def draw_aligned_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        pos_x: int,
        pos_y: int,
        font_family: str,
        font_size: int,
        fill_color: str,
        align: str = "center",
        max_width: Optional[int] = None
    ):
        """
        Draws text accurately with auto-scaling and atomic multi-line wrapping.
        Guarantees that words and academic titles (Prof., Dr., gelar) never break awkwardly.
        """
        if not text:
            return

        effective_max_width = max_width or 1600

        # Step A: Auto-scale font size down slightly if overflowing single line
        current_size = font_size
        min_auto_size = max(14, int(font_size * 0.70))
        font = self._get_font(font_family, current_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]

        while text_w > effective_max_width and current_size > min_auto_size:
            current_size -= 2
            font = self._get_font(font_family, current_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]

        # Step B: Smart atomic multi-line wrap if still exceeding max_width
        lines = self._smart_wrap_text(text, font, draw, effective_max_width)

        # Calculate line height & total block height
        sample_bbox = draw.textbbox((0, 0), "Aj", font=font)
        single_line_h = sample_bbox[3] - sample_bbox[1]
        line_spacing = int(single_line_h * 1.35)
        total_block_h = len(lines) * line_spacing

        if align == "center":
            start_y = pos_y - (total_block_h // 2) + (single_line_h // 2)
        elif align == "right":
            start_y = pos_y
        else:  # left
            start_y = pos_y

        for idx, line in enumerate(lines):
            l_bbox = draw.textbbox((0, 0), line, font=font)
            l_w = l_bbox[2] - l_bbox[0]
            l_y = start_y + (idx * line_spacing) - (single_line_h // 2)

            if align == "center":
                l_x = pos_x - (l_w // 2)
            elif align == "right":
                l_x = pos_x - l_w
            else:
                l_x = pos_x

            draw.text((l_x, l_y), line, font=font, fill=fill_color)

    def _resolve_dynamic_value(self, key: str, dynamic_values: Dict[str, Any]) -> str:
        """Smart matching for template parameters ignoring case and underscores"""
        if key in dynamic_values and dynamic_values[key] is not None:
            return str(dynamic_values[key])
        
        k_clean = key.lower().replace("_", "").replace("-", "").replace(" ", "")
        for dk, dv in dynamic_values.items():
            if dv is not None and dk.lower().replace("_", "").replace("-", "").replace(" ", "") == k_clean:
                return str(dv)
        return ""

    def render(
        self,
        template_bytes: bytes,
        fields_config: List[Dict[str, Any]],
        dynamic_values: Dict[str, Any],
        signature_bytes: Optional[bytes] = None,
        signature_config: Optional[Dict[str, Any]] = None,
        qr_config: Optional[Dict[str, Any]] = None,
        cert_number_config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bytes, str]:
        """
        Renders complete certificate on demand.
        Returns:
            Tuple of (output_image_bytes, sha256_checksum)
        """
        # 1. Load background naked certificate image and standardize to 1920x1080
        base_image = Image.open(io.BytesIO(template_bytes)).convert("RGBA")
        if base_image.size != (1920, 1080):
            base_image = base_image.resize((1920, 1080), Image.Resampling.LANCZOS)
        canvas_width, canvas_height = base_image.size
        draw = ImageDraw.Draw(base_image)

        # 2. Render dynamic text placeholders
        for field in fields_config:
            key = field.get("field_key", "")
            value = self._resolve_dynamic_value(key, dynamic_values)
            if not value or value.lower() == "none" or value.lower() == "nan":
                continue

            pos_x = field.get("pos_x", canvas_width // 2)
            pos_y = field.get("pos_y", canvas_height // 2)
            font_size = field.get("font_size", 36)
            font_color = field.get("font_color", "#1E293B")
            font_family = field.get("font_family", "DejaVuSans-Bold.ttf")
            align = field.get("text_align", "center")
            max_width = field.get("max_width")

            self.draw_aligned_text(
                draw=draw,
                text=value,
                pos_x=pos_x,
                pos_y=pos_y,
                font_family=font_family,
                font_size=font_size,
                fill_color=font_color,
                align=align,
                max_width=max_width
            )

        # 3. Render Auto-numbering serial code
        if cert_number_config and cert_number_config.get("number"):
            cert_num = cert_number_config.get("number")
            num_x = cert_number_config.get("pos_x")
            num_y = cert_number_config.get("pos_y")
            num_size = cert_number_config.get("font_size", 24)
            num_color = cert_number_config.get("color", "#1E293B")

            if num_x is not None and num_y is not None:
                self.draw_aligned_text(
                    draw=draw,
                    text=f"No: {cert_num}",
                    pos_x=num_x,
                    pos_y=num_y,
                    font_family="DejaVuSans.ttf",
                    font_size=num_size,
                    fill_color=num_color,
                    align="center"
                )

        # 4. Render Signature (Transparent PNG overlay)
        if signature_bytes and signature_config:
            try:
                sig_img = Image.open(io.BytesIO(signature_bytes)).convert("RGBA")
                sig_w = signature_config.get("width") or 200
                sig_h = signature_config.get("height") or 100
                sig_x = signature_config.get("pos_x", 100)
                sig_y = signature_config.get("pos_y", 100)

                sig_img = sig_img.resize((sig_w, sig_h), Image.Resampling.LANCZOS)
                base_image.paste(sig_img, (sig_x, sig_y), mask=sig_img)
            except Exception as e:
                logger.error(f"Failed to composite signature: {e}")

        # 5. Render Verification QR Code (Centered at pos_x, pos_y to match canvas)
        if qr_config and qr_config.get("url"):
            try:
                qr_url = qr_config.get("url")
                qr_size = qr_config.get("size", 150)
                qr_x = qr_config.get("pos_x", canvas_width - (qr_size // 2) - 40)
                qr_y = qr_config.get("pos_y", canvas_height - (qr_size // 2) - 40)

                qr_img = self.generate_qr_code(qr_url, size=qr_size)
                paste_x = qr_x - (qr_size // 2)
                paste_y = qr_y - (qr_size // 2)
                base_image.paste(qr_img, (paste_x, paste_y), mask=qr_img)
            except Exception as e:
                logger.error(f"Failed to composite QR code: {e}")

        # 6. Export to PNG bytes and calculate SHA-256 Checksum
        output_buffer = io.BytesIO()
        # Convert RGBA to RGB for standard image output
        rgb_image = Image.new("RGB", base_image.size, (255, 255, 255))
        rgb_image.paste(base_image, mask=base_image.split()[3])  # 3 is the alpha channel
        rgb_image.save(output_buffer, format="PNG", optimize=True)

        rendered_bytes = output_buffer.getvalue()
        sha256_hash = hashlib.sha256(rendered_bytes).hexdigest()

        return rendered_bytes, sha256_hash


cert_generator = CertificateGenerator()
