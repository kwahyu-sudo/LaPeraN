import base64
with open('templates/template_laporan.docx', 'rb') as f:
    data = f.read()
b64 = base64.b64encode(data).decode('ascii')
with open('templates/template_data.py', 'w') as f:
    f.write(f'TEMPLATE_B64 = "{b64}"\n')
print("Successfully generated template_data.py")
