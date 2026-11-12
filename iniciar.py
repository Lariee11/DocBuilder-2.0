"""
Inicia o DocBuilder: API (FastAPI/Uvicorn, porta 8000) e frontend (Vite) e abre a página no navegador.

Uso:  python iniciar.py
Para encerrar, pressione Ctrl+C nesta janela (os dois servidores são finalizados juntos).

- Usa o Python da pasta .venv, se existir (senão, o Python que executou este script).
- Usa o Node da pasta node_portable, se existir (senão, o Node instalado no sistema).
- Instala as dependências do frontend (npm install) se a pasta node_modules não existir.
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
API_PORT = 8000
IS_WINDOWS = os.name == "nt"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
VITE_URL_RE = re.compile(r"Local:\s+(https?://\S+)")


def python_executable():
    candidates = [os.path.join(ROOT, ".venv", "Scripts", "python.exe"), os.path.join(ROOT, ".venv", "bin", "python")]
    for path in candidates:
        if os.path.exists(path):
            return path
    return sys.executable


def node_environment():
    env = os.environ.copy()
    portable = os.path.join(ROOT, "node_portable")
    if os.path.isdir(portable):
        env["PATH"] = portable + os.pathsep + env.get("PATH", "")
    npm = shutil.which("npm", path=env["PATH"])
    if not npm:
        sys.exit("[ERRO] npm não encontrado. Instale o Node.js ou coloque a pasta node_portable no projeto.")
    return env, npm


def start(name, cmd, env=None):
    kwargs = {"cwd": ROOT, "env": env, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
              "text": True, "encoding": "utf-8", "errors": "replace", "bufsize": 1}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    print(f"[{name}] {' '.join(cmd)}")
    return subprocess.Popen(cmd, **kwargs)


def relay_output(name, proc, on_line=None):
    for line in proc.stdout:
        line = line.rstrip()
        print(f"[{name}] {line}")
        if on_line:
            on_line(ANSI_RE.sub("", line))


def stop(proc):
    if proc.poll() is not None:
        return
    if IS_WINDOWS:
        # Encerra o processo e os filhos (npm abre o node em um processo separado)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def wait_api(timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{API_PORT}/docs", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    print("=" * 50)
    print("  DocBuilder - iniciando servidores")
    print("=" * 50)

    env, npm = node_environment()
    if not os.path.isdir(os.path.join(ROOT, "node_modules")):
        print("[WEB] Instalando dependências do frontend (npm install)...")
        if subprocess.run([npm, "install"], cwd=ROOT, env=env).returncode != 0:
            sys.exit("[ERRO] Falha no npm install.")

    api = start("API", [python_executable(), "-m", "uvicorn", "api:app", "--reload", "--port", str(API_PORT)])
    web = start("WEB", [npm, "run", "dev"], env=env)

    web_url = {}
    url_found = threading.Event()

    def on_web_line(line):
        m = VITE_URL_RE.search(line)
        if m and not url_found.is_set():
            web_url["url"] = m.group(1)
            url_found.set()

    threading.Thread(target=relay_output, args=("API", api), daemon=True).start()
    threading.Thread(target=relay_output, args=("WEB", web, on_web_line), daemon=True).start()

    def open_page():
        if not url_found.wait(timeout=120):
            print("[ERRO] O frontend não informou o endereço da página. Verifique as mensagens [WEB] acima.")
            return
        if not wait_api():
            print("[AVISO] A API não respondeu na porta 8000; a página será aberta mesmo assim.")
        print(f"\n>>> DocBuilder disponível em {web_url['url']}  (Ctrl+C para encerrar)\n")
        webbrowser.open(web_url["url"])

    threading.Thread(target=open_page, daemon=True).start()

    try:
        while True:
            if api.poll() is not None:
                print(f"[ERRO] A API foi encerrada (código {api.returncode}).")
                break
            if web.poll() is not None:
                print(f"[ERRO] O frontend foi encerrado (código {web.returncode}).")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        stop(web)
        stop(api)
        print("Servidores finalizados.")


if __name__ == "__main__":
    main()
