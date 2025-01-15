#
# Copyright: https://github.com/mlcommons/ck/blob/master/cm-mlops/COPYRIGHT.md
# License: https://github.com/mlcommons/ck/blob/master/cm-mlops/LICENSE.md
#
# White paper: https://arxiv.org/abs/2406.16791
# History: https://github.com/mlcommons/ck/blob/master/HISTORY.CM.md
# Original repository: https://github.com/mlcommons/ck/tree/master/cm-mlops
#
# CK and CM project contributors: https://github.com/mlcommons/ck/blob/master/CONTRIBUTING.md
#

from cmind import utils
import os


def preprocess(i):

    os_info = i['os_info']
    env = i['env']

    path = env.get('RGAT_CHECKPOINT_PATH', '').strip()

    if path == '' or not os.path.exists(path):
        env['CM_TMP_REQUIRE_DOWNLOAD'] = 'yes'

    return {'return': 0}


def postprocess(i):

    env = i['env']

    if env.get('RGAT_CHECKPOINT_PATH', '') == '':
        env['RGAT_CHECKPOINT_PATH'] = os.path.join(
            env['CM_ML_MODEL_PATH'], "RGAT.pt")
    elif env.get('CM_ML_MODEL_PATH', '') == '':
        env['CM_ML_MODEL_PATH'] = env['RGAT_CHECKPOINT_PATH']

    env['CM_GET_DEPENDENT_CACHED_PATH'] = env['RGAT_CHECKPOINT_PATH']

    return {'return': 0}
