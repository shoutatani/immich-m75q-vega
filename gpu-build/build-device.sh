#!/bin/bash
set -euo pipefail
cd /work
# AMD公式ソース13ファイルを、既存2.15.0のABIに合わせてgfx900向けにビルドする。
for source_file in source/src/targets/gpu/device/*.cpp; do
  object_file="device-build/objects/$(basename "$source_file" .cpp).o"
  echo "コンパイル: $source_file"
  /opt/rocm/bin/hipcc -std=c++17 -O2 -DNDEBUG -fPIC --offload-arch=gfx900 \
    -fno-gpu-rdc -Wno-cuda-compat -Wno-unused-command-line-argument \
    -Xclang -fnative-half-arguments-and-returns \
    -Dmigraphx_device_EXPORTS \
    -Idevice-build/generated \
    -Imigraphx-dev/opt/rocm-7.2.0/include \
    -Imigraphx-dev/opt/rocm-7.2.0/lib/migraphx/include \
    -Isource/src/targets/gpu/device/include \
    -Isource/src/targets/gpu/include \
    -c "$source_file" -o "$object_file"
done
/opt/rocm/bin/hipcc -shared -fPIC --offload-arch=gfx900 -fno-gpu-rdc \
  -Wl,-soname,libmigraphx_device.so.2015000 '-Wl,-rpath,$ORIGIN' \
  device-build/objects/*.o \
  /opt/rocm/lib/migraphx/lib/libmigraphx.so.2015000 \
  -o device-build/libmigraphx_device.so.2015000.0.70200
ls -lh device-build/libmigraphx_device.so.2015000.0.70200
