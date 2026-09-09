$ErrorActionPreference = "Stop"

$token = Read-Host "Nhap NGROK_AUTHTOKEN cua ban"
if ([string]::IsNullOrWhiteSpace($token)) {
    throw "NGROK_AUTHTOKEN khong duoc de trong."
}

ngrok config add-authtoken $token
Write-Host "Da cau hinh ngrok authtoken thanh cong." -ForegroundColor Green
Write-Host "Chay dashboard bang lenh: python run_with_ngrok.py" -ForegroundColor Cyan
