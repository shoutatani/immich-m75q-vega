FROM ghcr.io/immich-app/immich-machine-learning:v3.3.1-rocm@sha256:0936fa0414903164315c9c80a9f2c2a6ed9b8387ce05decbfe606d1d54e7a2ca
LABEL org.opencontainers.image.source="https://github.com/shoutatani/immich-m75q-vega"
LABEL org.opencontainers.image.licenses="AGPL-3.0"
# rocBLAS本体は7.2.0を維持し、旧版からgfx900演算データだけ追加。
COPY .build/rocblas-extracted/opt/rocm-6.3.4/lib/rocblas/library/ /opt/rocm/lib/rocblas/library/
COPY .build/device-build/libmigraphx_device.so.2015000.0.70200 /opt/rocm/lib/migraphx/lib/libmigraphx_device.so.2015000.0.70200
COPY checks/ /opt/immich-m75q/checks/
COPY samples/ /opt/immich-m75q/samples/
