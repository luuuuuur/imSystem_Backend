# Puedes usar este código en Python para generar la imagen tú mismo de forma segura:
import qrcode
url = "otpauth://totp/IMS%20Sistema:test_totp?secret=B22N7GQ5XSL65GJYBWU5E4NY7ARFZXYJ&issuer=IMS%20Sistema"
qr = qrcode.QRCode(version=1, box_size=10, border=5)
qr.add_data(url)
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")
img.save("totp_qr.png")
