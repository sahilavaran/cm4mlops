export PATH=${CM_CONDA_BIN_PATH}:$PATH

cd ${CM_HARNESS_CODE_ROOT}


export CMAKE_PREFIX_PATH=${CONDA_PREFIX:-"$(dirname $(which conda))/../"}

export IPEX_PATH=${CM_IPEX_INSTALLED_PATH}
export TORCH_PATH=`python -c 'import torch;print(torch.utils.cmake_prefix_path)'`

if [[ -z ${TORCH_PATH} ]]; then
  echo "Torch not found"
  exit 1
fi

export LOADGEN_DIR="${CM_MLPERF_INFERENCE_LOADGEN_INSTALL_PATH}/../"
export OPENCV_DIR=${CM_OPENCV_BUILD_PATH}
export RAPIDJSON_INCLUDE_DIR=${CM_RAPIDJSON_SRC_REPO_PATH}/include
export GFLAGS_DIR=${CM_GFLAGS_BUILD_PATH}
export USE_CUDA=0

BUILD_DIR=${PWD}/build
rm -rf "$BUILD_DIR"

SRC_DIR=${PWD}/src

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${OPENCV_DIR}/lib:${ONEDNN_DIR}/build/src
export LIBRARY_PATH=${LIBRARY_PATH}:${CONDA_PREFIX}/lib

cmd="cmake -DCMAKE_PREFIX_PATH=${TORCH_PATH} \
    -DLOADGEN_DIR=${LOADGEN_DIR} \
    -DOpenCV_DIR=${OPENCV_DIR} \
    -DRapidJSON_INCLUDE_DIR=${RAPIDJSON_INCLUDE_DIR} \
    -Dgflags_DIR=${GFLAGS_DIR} \
    -DINTEL_EXTENSION_FOR_PYTORCH_PATH=${IPEX_PATH} \
    -DCMAKE_BUILD_TYPE=Release \
    -B${BUILD_DIR} \
    -H${SRC_DIR}"
echo "$cmd"
eval "$cmd"
test "$?" -eq 0 || exit "$?"

cmake --build ${BUILD_DIR} --config Release -j$(nproc)
test "$?" -eq 0 || exit "$?"
