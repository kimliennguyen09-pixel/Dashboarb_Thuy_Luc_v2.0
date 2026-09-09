"""Khởi chạy dashboard và tạo public URL bằng ngrok."""
import os
import subprocess
import sys
import time
import urllib.request


def wait_for_server(port: int, timeout: int = 20) -> None:
    """Chỉ mở tunnel sau khi Flask API thực sự sẵn sàng."""
    deadline = time.time() + timeout
    health_url = f"http://127.0.0.1:{port}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.4)
    raise RuntimeError(f"Flask API chưa sẵn sàng sau {timeout} giây.")


def main():
    try:
        from pyngrok import ngrok
    except ImportError:
        raise SystemExit("Thiếu pyngrok. Chạy: python -m pip install -r requirements.txt")

    port = int(os.getenv("DASHBOARD_PORT", "8000"))
    token = os.getenv("NGROK_AUTHTOKEN", "").strip()
    if token:
        ngrok.set_auth_token(token)
    project_dir = os.path.dirname(os.path.abspath(__file__))
    process = subprocess.Popen([sys.executable, "api.py"], cwd=project_dir)
    try:
        wait_for_server(port)
        tunnel = ngrok.connect(addr=port, proto="http", bind_tls=True)
        print(f"\nDashboard local: http://127.0.0.1:{port}")
        print(f"Dashboard ngrok: {tunnel.public_url}\n")
        process.wait()
    except Exception as error:
        raise SystemExit(f"Không thể chạy dashboard/ngrok: {error}") from error
    except KeyboardInterrupt:
        pass
    finally:
        ngrok.kill()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
