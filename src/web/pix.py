"""Pix "copia e cola" (BR Code estático) e QR code em SVG, sem depender de serviço externo.

O payload segue o padrão EMV QRCPS-MPM do Manual de Padrões para Iniciação do Pix (BCB):
cada campo é ID (2 dígitos) + tamanho (2 dígitos) + valor, e o código termina com um
CRC16-CCITT (polinômio 0x1021, valor inicial 0xFFFF) calculado sobre todo o resto.
"""
import unicodedata
from base64 import b64encode
from decimal import Decimal


def _campo(id_, valor):
    valor = str(valor)
    if len(valor) > 99:
        raise ValueError(f"Campo {id_} do Pix passou de 99 caracteres.")
    return f"{id_}{len(valor):02d}{valor}"


def _ascii_maiusculo(texto, limite):
    """Nome e cidade do recebedor: sem acento, maiúsculo e dentro do limite do padrão."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.upper().strip()[:limite]


def crc16_ccitt(dados: str) -> str:
    crc = 0xFFFF
    for byte in dados.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def payload_pix(chave, nome, cidade, txid="***", descricao="", valor=None):
    """Monta o código "Pix copia e cola" de um QR estático.

    ``valor=None`` deixa o leitor escolher quanto doar.
    """
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", chave.strip())
    if descricao:
        conta += _campo("02", descricao[:40])

    payload = (
        _campo("00", "01")                       # versão do payload
        + _campo("26", conta)                    # dados da conta Pix
        + _campo("52", "0000")                   # categoria do comerciante
        + _campo("53", "986")                    # moeda: real
        + (_campo("54", f"{Decimal(valor):.2f}") if valor else "")
        + _campo("58", "BR")
        + _campo("59", _ascii_maiusculo(nome, 25))
        + _campo("60", _ascii_maiusculo(cidade, 15))
        + _campo("62", _campo("05", txid[:25]))  # identificador da transação
        + "6304"                                 # CRC vem a seguir
    )
    return payload + crc16_ccitt(payload)


def qr_svg_data_uri(texto):
    """QR code em SVG embutido como data URI (sem arquivo e sem Pillow)."""
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, border=2, box_size=10)
    return "data:image/svg+xml;base64," + b64encode(img.to_string()).decode()
