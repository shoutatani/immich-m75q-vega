#!/usr/bin/env python3
"""専用ディレクトリにImmichを構築する。既存環境を上書きしない。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = 'ghcr.io/immich-app/immich-machine-learning:v3.2.0-rocm@sha256:ec7d7ec1e624571edd92efd0c4820c8eda91c21956140b87fc2af93e0f33dc86'
MARKER = '.m75q-instance.json'
DOWNLOADS = {
    'rocblas.deb': ('https://repo.radeon.com/rocm/apt/6.3.4/pool/main/r/rocblas/rocblas_4.3.0.60304-76~24.04_amd64.deb', '280fc07652f998046fdcfa68dcde9708c82860269c53e3ca83bd3d164a7a2c32'),
    'migraphx-dev.deb': ('https://repo.radeon.com/rocm/apt/7.2/pool/main/m/migraphx-dev/migraphx-dev_2.15.0.70200-43~24.04_amd64.deb', 'd99155727eae05a41f631c179dc1092724c1be256172b31aa5c487247c192072'),
    'source.tar.gz': ('https://codeload.github.com/ROCm/AMDMIGraphX/tar.gz/refs/tags/rocm-7.2.0', '085ea6fcf6197b20fed60917194ca622e5d2c1705237fe063563f988494a8b3d'),
}

def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)

def capture(args, **kwargs):
    return subprocess.check_output([str(x) for x in args], text=True, **kwargs).strip()

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def image_tag():
    h = hashlib.sha256()
    for folder in ['gpu-build', 'patches', 'checks', 'samples']:
        for path in sorted((ROOT / folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                h.update(str(path.relative_to(ROOT)).encode())
                h.update(path.read_bytes())
    return 'immich-m75q-vega-ml:v3.2.0-' + h.hexdigest()[:12]

def load_instance(directory):
    directory = Path(directory).expanduser().resolve()
    marker = directory / MARKER
    if not marker.is_file():
        raise ValueError('このツールで作成した導入先ではありません: ' + str(directory))
    state = json.loads(marker.read_text())
    if state.get('directory') != str(directory) or state.get('format') != 1:
        raise ValueError('導入先と管理情報が一致しません')
    if state.get('compose_sha256') != digest(directory / 'compose.yaml'):
        raise ValueError('compose.yamlが変更されています。管理情報と差分を確認してください')
    return state

def initialize(directory, project, port, video_gid, render_gid, image, replace_image=False):
    directory = Path(directory).expanduser().resolve()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,49}', project) or not 1 <= port <= 65535:
        raise ValueError('プロジェクト名は小文字英数字・ハイフン・下線、ポートは1〜65535で指定してください')
    expected = dict(format=1, directory=str(directory), project=project, port=port, image=image)
    if (directory / MARKER).exists():
        state = load_instance(directory)
        if any(state.get(k) != v for k, v in expected.items() if k != 'image'):
            raise ValueError('既存の導入設定と異なります。別の新規ディレクトリを指定してください')
        if state['image'] != image:
            if not replace_image:
                raise ValueError('推論イメージのソースが変わっています。再構築する場合は --rebuild を指定してください')
            env_path = directory / '.env'
            env = env_path.read_text()
            old_line = 'IMMICH_ML_IMAGE=' + state['image'] + '\n'
            new_line = 'IMMICH_ML_IMAGE=' + image + '\n'
            if old_line not in env and new_line not in env:
                raise ValueError('.envの推論イメージと管理情報が一致しません')
            env_path.write_text(env.replace(old_line,new_line))
            state['image'] = image
            (directory / MARKER).write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
        return state
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('空でない導入先には書き込みません: ' + str(directory))
    directory.mkdir(parents=True, exist_ok=True)
    for name in ['library', 'postgres', 'evidence']:
        (directory / name).mkdir()
    shutil.copyfile(ROOT / 'compose.yaml', directory / 'compose.yaml')
    env = '\n'.join([
        'COMPOSE_PROJECT_NAME=' + project,
        'IMMICH_VERSION=v3.2.0',
        'UPLOAD_LOCATION=./library',
        'DB_DATA_LOCATION=./postgres',
        'DB_USERNAME=postgres',
        'DB_DATABASE_NAME=immich',
        'DB_PASSWORD=' + secrets.token_hex(24),
        'IMMICH_HTTP_PORT=' + str(port),
        'IMMICH_ML_IMAGE=' + image,
        'IMMICH_VIDEO_GID=' + str(video_gid),
        'IMMICH_RENDER_GID=' + str(render_gid), '',
    ])
    fd = os.open(directory / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(env)
    expected['compose_sha256'] = digest(directory / 'compose.yaml')
    (directory / MARKER).write_text(json.dumps(expected, ensure_ascii=False, indent=2) + '\n')
    return expected

def compose(directory, *args):
    state = load_instance(directory)
    return ['docker', 'compose', '--project-directory', str(directory), '--env-file', str(directory / '.env'),
            '-p', state['project'], '-f', str(directory / 'compose.yaml'), *args]

def check_project(directory, project):
    ids = capture(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project]).split()
    if not ids:
        return
    containers = json.loads(capture(['docker', 'inspect', *ids]))
    for item in containers:
        working = item['Config']['Labels'].get('com.docker.compose.project.working_dir', '')
        if Path(working).resolve() != directory.resolve() or not (directory / MARKER).exists():
            raise ValueError('同名の別環境があります。別の --project を指定してください: ' + project)

def doctor(directory):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('実行対象はM75q-1上のLinux x86_64です。Macでは編集のみ行ってください')
    for command in ['docker', 'dpkg-deb', 'tar', 'python3', 'curl']:
        if not shutil.which(command):
            raise ValueError('必要なコマンドがありません: ' + command)
    cpu = Path('/proc/cpuinfo').read_text()
    if '3400GE' not in cpu:
        raise ValueError('検証対象のRyzen 5 3400GEを確認できませんでした')
    for device in ['/dev/kfd', '/dev/dri/renderD128']:
        if not Path(device).exists():
            raise ValueError('GPUデバイスがありません: ' + device)
    run(['docker', 'info', '--format', '{{.ServerVersion}}'])
    run(['docker', 'compose', 'version'])
    parent = directory
    while not parent.exists():
        parent = parent.parent
    free = shutil.disk_usage(parent).free / 1024**3
    print(f'導入先の空き容量: {free:.1f} GiB', flush=True)
    if free < 60:
        raise ValueError('導入先に60 GiB以上の空き容量を用意してください（100 GiB以上推奨）')
    docker_root = capture(['docker', 'info', '--format', '{{.DockerRootDir}}'])
    if os.path.exists(docker_root) and shutil.disk_usage(docker_root).free < 50 * 1024**3:
        raise ValueError('Docker保存先に50 GiB以上の空き容量が必要です')
    print('GPUデバイス・Docker・空き容量を確認しました', flush=True)

def download(path, url, expected):
    if path.exists() and digest(path) == expected:
        return
    temporary = path.with_suffix(path.suffix + '.part')
    print('取得: ' + path.name, flush=True)
    run(['curl', '-fL', '--retry', '3', '--connect-timeout', '30', '-o', temporary, url])
    if digest(temporary) != expected:
        raise ValueError('ダウンロードのSHA256が一致しません: ' + path.name)
    temporary.replace(path)

def build_image(image):
    build = ROOT / '.build'
    build.mkdir(exist_ok=True)
    for name, (url, checksum) in DOWNLOADS.items():
        download(build / name, url, checksum)
    for name in ['rocblas-extracted', 'migraphx-dev', 'source', 'device-build/objects', 'device-build/generated/migraphx/gpu/device']:
        (build / name).mkdir(parents=True, exist_ok=True)
    # パッケージは展開だけ行い、ホストにインストールしない。
    with (build / 'rocblas-files.tar').open('wb') as stream:
        run(['dpkg-deb', '--fsys-tarfile', build / 'rocblas.deb'], stdout=stream)
    run(['tar', '-xf', build / 'rocblas-files.tar', '-C', build / 'rocblas-extracted', '--wildcards', './opt/rocm-6.3.4/lib/rocblas/library/*gfx900*'])
    (build / 'rocblas-files.tar').unlink()
    run(['dpkg-deb', '-x', build / 'migraphx-dev.deb', build / 'migraphx-dev'])
    run(['tar', '-xzf', build / 'source.tar.gz', '-C', build / 'source', '--strip-components=1'])
    template = (build / 'source/src/targets/gpu/device/targets.hpp.in').read_text()
    (build / 'device-build/generated/migraphx/gpu/device/targets.hpp').write_text(template.replace('@GPU_TARGETS@', 'gfx900'))
    shutil.copyfile(ROOT / 'gpu-build/build-device.sh', build / 'build-device.sh')
    shutil.copyfile(ROOT / 'gpu-build/check-device.py', build / 'check-device.py')
    run(['docker', 'pull', BASE])
    print('MIGraphXをgfx900向けにビルドします（数分〜十数分）', flush=True)
    run(['docker', 'run', '--rm', '--cpus=2', '--memory=6g', '--network=none', '--user', f'{os.getuid()}:{os.getgid()}',
         '-v', str(build) + ':/work', '-w', '/work', '--entrypoint', '/bin/bash', BASE, '/work/build-device.sh'])
    run(['docker', 'run', '--rm', '--network=none', '-v', str(build) + ':/work:ro', '--entrypoint', 'python', BASE, '/work/check-device.py'])
    run(['docker', 'build', '-f', ROOT / 'gpu-build/Dockerfile', '-t', image, ROOT])

def warmup(directory):
    print('OCRのGPU準備を開始します。初回は十数分〜数十分かかります', flush=True)
    run(compose(directory, 'run', '--rm', '--no-deps', '-T', '--entrypoint', 'python', 'immich-machine-learning', '/opt/immich-m75q/checks/warmup-ocr.py'))

def install(args, directory):
    doctor(directory)
    check_project(directory, args.project)
    if not (directory / MARKER).exists():
        with socket.socket() as sock:
            try:
                sock.bind(('0.0.0.0', args.port))
            except OSError as error:
                raise ValueError('指定ポートが使用中です。--portで未使用ポートを指定してください') from error
    import grp
    video = grp.getgrnam('video').gr_gid
    render = Path('/dev/kfd').stat().st_gid
    state = initialize(directory, args.project, args.port, video, render, image_tag(), replace_image=args.rebuild)
    run(compose(directory, 'config', '--quiet'))
    exists = subprocess.run(['docker', 'image', 'inspect', state['image']], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not exists or args.rebuild:
        build_image(state['image'])
    run(compose(directory, 'pull', 'immich-server', 'redis', 'database'))
    warmup(directory)
    run(compose(directory, 'up', '-d', '--wait', '--wait-timeout', '600'))
    deadline = time.monotonic() + 120
    while True:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{state["port"]}/api/server/ping', timeout=10) as response:
                if json.load(response).get('res') == 'pong':
                    break
        except (OSError, ValueError, urllib.error.URLError):
            pass
        if time.monotonic() >= deadline:
            raise ValueError('公開ポート経由でImmich APIに接続できません。compose logsで確認してください')
        time.sleep(3)
    print(f'導入完了: http://サーバーのIP:{state["port"]}\n初回アクセスで管理者を登録してください。\n導入先: {directory}', flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'doctor', 'warmup', 'status', 'verify', 'compose'], nargs='?', default='install')
    parser.add_argument('--directory', type=Path, default=Path.home() / 'immich-app')
    parser.add_argument('--project', default='immich-m75q')
    parser.add_argument('--port', type=int, default=2283)
    parser.add_argument('--rebuild', action='store_true')
    parser.add_argument('--initialize-test-admin', action='store_true', help='検証専用の新規環境にだけテスト管理者を作成')
    args, extra = parser.parse_known_args()
    directory = args.directory.expanduser().resolve()
    if args.command != 'compose' and extra:
        parser.error('不明な引数: ' + ' '.join(extra))
    if args.command == 'install':
        install(args, directory)
    elif args.command == 'doctor':
        doctor(directory)
    else:
        state = load_instance(directory)
        check_project(directory, state['project'])
        if args.command == 'warmup':
            warmup(directory)
        elif args.command == 'status':
            run(compose(directory, 'ps'))
        elif args.command == 'compose':
            if extra and extra[0] == '--':
                extra = extra[1:]
            run(compose(directory, *extra))
        elif args.command == 'verify':
            cmd = [sys.executable, ROOT / 'checks/verify-instance.py', '--directory', directory]
            if args.initialize_test_admin:
                cmd.append('--initialize-test-admin')
            run(cmd)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print('停止しました: ' + str(error), file=sys.stderr)
        sys.exit(1)
