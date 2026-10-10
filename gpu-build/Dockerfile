FROM ghcr.io/immich-app/immich-machine-learning:v3.2.0-rocm@sha256:ec7d7ec1e624571edd92efd0c4820c8eda91c21956140b87fc2af93e0f33dc86
LABEL org.opencontainers.image.source="https://github.com/shoutatani/immich-m75q-vega"
LABEL org.opencontainers.image.licenses="AGPL-3.0"
# rocBLAS本体は7.2.0を維持し、旧版からgfx900演算データだけ追加。
COPY .build/rocblas-extracted/opt/rocm-6.3.4/lib/rocblas/library/ /opt/rocm/lib/rocblas/library/
COPY .build/device-build/libmigraphx_device.so.2015000.0.70200 /opt/rocm/lib/migraphx/lib/libmigraphx_device.so.2015000.0.70200
# 固定したImmich v3.2.0用のソース修正。
COPY patches/ort.py /usr/src/immich_ml/sessions/ort.py
COPY patches/detection.py /usr/src/immich_ml/models/ocr/detection.py
COPY patches/recognition.py /usr/src/immich_ml/models/ocr/recognition.py
COPY checks/ /opt/immich-m75q/checks/
COPY samples/ /opt/immich-m75q/samples/
