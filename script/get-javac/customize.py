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

    automation = i['automation']

    recursion_spaces = i['recursion_spaces']

    run_script_input = i['run_script_input']

    file_name = 'javac.exe' if os_info['platform'] == 'windows' else 'javac'

    cur_dir = os.getcwd()

    meta = i['meta']

    found = False
    install = env.get('CM_JAVAC_PREBUILT_INSTALL', '') in ['on', 'True', True]

    env_path_key = 'CM_JAVAC_BIN_WITH_PATH'

    # If not force install, search for artifact
    if not install:
        rr = i['automation'].find_artifact({'file_name': file_name,
                                           'env': env,
                                            'os_info': os_info,
                                            'default_path_env_key': 'PATH',
                                            'detect_version': True,
                                            'env_path_key': env_path_key,
                                            'run_script_input': i['run_script_input'],
                                            'hook': skip_path,
                                            'recursion_spaces': recursion_spaces})
        if rr['return'] == 0:
            found = True
        elif rr['return'] != 16:
            return rr

    # If not found or force install
    if not found or install:

        if os_info['platform'] == 'windows':
            env['CM_JAVAC_PREBUILT_HOST_OS'] = 'windows'
            env['CM_JAVAC_PREBUILT_EXT'] = '.zip'
        else:
            env['CM_JAVAC_PREBUILT_HOST_OS'] = 'linux'
            env['CM_JAVAC_PREBUILT_EXT'] = '.tar.gz'

        url = env['CM_JAVAC_PREBUILT_URL']
        filename = env['CM_JAVAC_PREBUILT_FILENAME']

        javac_prebuilt_version = env['CM_JAVAC_PREBUILT_VERSION']
        javac_prebuilt_build = env['CM_JAVAC_PREBUILT_BUILD']

        for key in ['CM_JAVAC_PREBUILT_VERSION',
                    'CM_JAVAC_PREBUILT_BUILD',
                    'CM_JAVAC_PREBUILT_HOST_OS',
                    'CM_JAVAC_PREBUILT_EXT']:
            url = url.replace('${' + key + '}', env[key])
            filename = filename.replace('${' + key + '}', env[key])

        env['CM_JAVAC_PREBUILT_URL'] = url
        env['CM_JAVAC_PREBUILT_FILENAME'] = filename

        print('')
        print(
            recursion_spaces +
            '    Downloading and installing prebuilt Java from {} ...'.format(
                url +
                filename))

        rr = automation.run_native_script(
            {'run_script_input': run_script_input, 'env': env, 'script_name': 'install-prebuilt'})
        if rr['return'] > 0:
            return rr

        target_path = os.path.join(
            cur_dir, 'jdk-' + java_prebuilt_version, 'bin')
        target_file = os.path.join(target_path, file_name)

        if not os.path.isfile(target_file):
            return {'return': 1,
                    'error': 'can\'t find target file {}'.format(target_file)}

        print('')
        print(
            recursion_spaces +
            '    Registering file {} ...'.format(target_file))

        env[env_path_key] = target_file

        if '+PATH' not in env:
            env['+PATH'] = []
        env['+PATH'].append(target_path)

    return {'return': 0}


def skip_path(i):

    # Avoid not complete path on Windows
    skip = False

    path = i['file']

    if 'javapath' in path:
        skip = True

    return {'return': 0, 'skip': skip}


def detect_version(i):

    r = i['automation'].parse_version({'match_text': r'javac\s*([\d.]+)',
                                       'group_number': 1,
                                       'env_key': 'CM_JAVAC_VERSION',
                                       'which_env': i['env'],
                                       'debug': True})
    if r['return'] > 0:
        return r

    version = r['version']

    print(i['recursion_spaces'] + '    Detected version: {}'.format(version))

    return {'return': 0, 'version': version}


def postprocess(i):

    os_info = i['os_info']

    env = i['env']
    r = detect_version(i)
    if r['return'] > 0:
        return r

    version = env['CM_JAVAC_VERSION']
    env['CM_JAVAC_CACHE_TAGS'] = 'version-' + version

    found_file_path = env['CM_JAVAC_BIN_WITH_PATH']
    file_name = os.path.basename(found_file_path)
    file_path = os.path.dirname(found_file_path)

    env['CM_JAVAC_BIN'] = file_name

    if os_info['platform'] == 'windows':
        env['CM_JAVA_BIN'] = 'java.exe'
    else:
        env['CM_JAVA_BIN'] = 'java'

    env['CM_JAVA_BIN_WITH_PATH'] = os.path.join(file_path, env['CM_JAVA_BIN'])

    found_path = os.path.dirname(found_file_path)
    javac_home_path = os.path.dirname(found_path)

    env['JAVA_HOME'] = javac_home_path

    return {'return': 0, 'version': version}
