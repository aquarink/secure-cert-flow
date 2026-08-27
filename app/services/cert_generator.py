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

    def draw_aligned_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        pos_x: int,
        pos_y: int,
        font: ImageFont.ImageFont,
        fill_color: str,
        align: str = "center"
    ):
        """Draws text accurately with Left, Center, or Right alignment"""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if align == "center":
            draw_x = pos_x - (text_width // 2)
            draw_y = pos_y - (text_height // 2)
        elif align == "right":
            draw_x = pos_x - text_width
            draw_y = pos_y
        else:  # left
            draw_x = pos_x
            draw_y = pos_y

        draw.text((draw_x, draw_y), text, font=font, fill=fill_color)

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

            font = self._get_font(font_family, font_size)
            self.draw_aligned_text(draw, value, pos_x, pos_y, font, font_color, align)

        # 3. Render Auto-numbering serial code
        if cert_number_config and cert_number_config.get("number"):
            cert_num = cert_number_config.get("number")
            num_x = cert_number_config.get("pos_x")
            num_y = cert_number_config.get("pos_y")
            num_size = cert_number_config.get("font_size", 24)
            num_color = cert_number_config.get("color", "#1E293B")

            if num_x is not None and num_y is not None:
                num_font = self._get_font("DejaVuSans.ttf", num_size)
                self.draw_aligned_text(draw, f"No: {cert_num}", num_x, num_y, num_font, num_color, "center")

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
