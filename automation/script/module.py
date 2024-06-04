import os
import utils
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# CM "script" automation helps users to encode their MLOps, DevOps and other knowledge
# as portable and reusable automation recipes with simple tags, native scripts

class CAutomation:
    def __init__(self, cmind, path):
        self.cmind = cmind
        self.path = path

    def _run_deps(self, deps, clean_env_keys_deps, env, state, const, const_state, add_deps_recursive, recursion_spaces, remembered_selections, variation_tags_string='', from_cache=False, debug_script_tags='', verbose=False, show_time=False, extra_recursion_spaces='  ', run_state={'deps':[], 'fake_deps':[], 'parent': None}):
        """
        Runs all the enabled dependencies and pass them env minus local env
        """
        if len(deps) > 0:
            # Preserve local env
            tmp_env = {}

            variation_groups = run_state.get('variation_groups')

            for d in deps:
                if not d.get('tags'):
                    continue

                if d.get('skip_if_fake_run', False) and env.get('CM_TMP_FAKE_RUN','')=='yes':
                    continue

                if "enable_if_env" in d:
                    if not enable_or_skip_script(d["enable_if_env"], env):
                        continue

                if "enable_if_any_env" in d:
                    if not any_enable_or_skip_script(d["enable_if_any_env"], env):
                        continue

                if "skip_if_env" in d:
                    if enable_or_skip_script(d["skip_if_env"], env):
                        continue

                if "skip_if_any_env" in d:
                    x = any_enable_or_skip_script(d["skip_if_any_env"], env)
                    if x:
                        continue

                if from_cache and not d.get("dynamic", None):
                    continue

                update_tags_from_env_with_prefix = d.get("update_tags_from_env_with_prefix", {})
                for t in update_tags_from_env_with_prefix:
                    for key in update_tags_from_env_with_prefix[t]:
                        if str(env.get(key, '')).strip() != '':
                            d['tags']+=","+t+str(env[key])

                for key in clean_env_keys_deps:
                    if '?' in key or '*' in key:
                        import fnmatch
                        for kk in list(env.keys()):
                            if fnmatch.fnmatch(kk, key):
                                tmp_env[kk] = env[kk]
                                del(env[kk])
                    elif key in env:
                        tmp_env[key] = env[key]
                        del(env[key])

                import re
                for key in list(env.keys()):
                    value = env[key]
                    tmp_values = re.findall(r'<<<(.*?)>>>', str(value))
                    if tmp_values == []: continue
                    tmp_env[key] = env[key]
                    del(env[key])

                force_env_keys_deps = d.get("force_env_keys", [])
                for key in force_env_keys_deps:
                    if '?' in key or '*' in key:
                        import fnmatch
                        for kk in list(tmp_env.keys()):
                            if fnmatch.fnmatch(kk, key):
                                env[kk] = tmp_env[kk]
                    elif key in tmp_env:
                        env[key] = tmp_env[key]

                if d.get("reuse_version", False):
                    for k in tmp_env:
                        if k.startswith('CM_VERSION'):
                            env[k] = tmp_env[k]

                update_tags_from_env = d.get("update_tags_from_env", [])
                for t in update_tags_from_env:
                    if env.get(t, '').strip() != '':
                        d['tags']+=","+env[t]

                inherit_variation_tags = d.get("inherit_variation_tags", False)
                skip_inherit_variation_groups = d.get("skip_inherit_variation_groups", [])
                variation_tags_to_be_skipped = []
                if inherit_variation_tags:
                    if skip_inherit_variation_groups: #skips inheriting variations belonging to given groups
                        for group in variation_groups:
                            if group in skip_inherit_variation_groups:
                                variation_tags_to_be_skipped += variation_groups[group]['variations']

                    variation_tags = variation_tags_string.split(",")
                    variation_tags =  [ x for x in variation_tags if not x.startswith("_") or x[1:] not in set(variation_tags_to_be_skipped) ]

                    # handle group in case of dynamic variations
                    for t_variation in variation_tags_to_be_skipped:
                        if t_variation.endswith(".#"):
                            beg = t_variation[:-1]
                            for m_tag in variation_tags:
                                if m_tag.startswith("_"+beg):
                                    variation_tags.remove(m_tag)

                    deps_tags = d['tags'].split(",")
                    for tag in deps_tags:
                        if tag.startswith("-_") or tag.startswith("_-"):
                            variation_tag = "_" + tag[2:]
                            if variation_tag in variation_tags:
                                variation_tags.remove(variation_tag)
                    new_variation_tags_string = ",".join(variation_tags)
                    d['tags']+=","+new_variation_tags_string #deps should have non-empty tags

                run_state['deps'].append(d['tags'])

                if not run_state['fake_deps']:
                    import copy
                    tmp_run_state_deps = copy.deepcopy(run_state['deps'])
                    run_state['deps'] = []
                    tmp_parent = run_state['parent']

                    run_state['parent'] = run_state['script_id']

                    if len(run_state['script_variation_tags']) > 0:
                        run_state['parent'] += " ( " + ',_'.join(run_state['script_variation_tags']) + " )"

                    tmp_script_id = run_state['script_id']
                    tmp_script_variation_tags = run_state['script_variation_tags']

                    # Run collective script via CM API:
                    # Not very efficient but allows logging - can be optimized later

                    ii = {
                            'action':'run',
                            'automation':utils.assemble_cm_object(self.meta['alias'], self.meta['uid']),
                            'recursion_spaces':recursion_spaces, # + extra_recursion_spaces,
                            'recursion':True,
                            'remembered_selections': remembered_selections,
                            'env':env,
                            'state':state,
                            'const':const,
                            'const_state':const_state,
                            'add_deps_recursive':add_deps_recursive,
                            'debug_script_tags':debug_script_tags,
                            'verbose':verbose,
                            'silent':run_state.get('tmp_silent', False),
                            'time':show_time,
                            'run_state':run_state

                        }

                    for key in [ "env", "state", "const", "const_state" ]:
                        ii['local_'+key] = d.get(key, {})
                        if d.get(key):
                            d[key] = {}

                    utils.merge_dicts({'dict1':ii, 'dict2':d, 'append_lists':True, 'append_unique':True})

                    r = update_env_with_values(ii['env']) #to update env local to a dependency
                    if r['return']>0: return r 

                    r = self.cmind.access(ii)
                    if r['return']>0: return r

                    run_state['deps'] = tmp_run_state_deps
                    run_state['parent'] = tmp_parent
                    run_state['script_id'] = tmp_script_id
                    run_state['script_variation_tags'] = tmp_script_variation_tags

                    # Restore local env
                    env.update(tmp_env)
                    r = update_env_with_values(env)
                    if r['return']>0: return r 

        return {'return': 0}

    def native_run(self, i):
        """
        Add CM script

        Args:
          (CM input dict): 

          env (dict): environment
          command (str): string
          ...

        Returns:
          (CM return dict):

          * return (int): return code == 0 if no error and >0 if error
          * (error) (str): error string if return>0

        """

        env = i.get('env', {})
        cmd = i.get('command', '')

        script = i.get('script',[])

        # Create temporary script name
        script_name = i.get('script_name','')
        if script_name=='': 
            script_name='tmp-native-run.'

            if os.name == 'nt':
                script_name+='bat'
            else:
                script_name+='sh'

        if os.name == 'nt':
            xcmd = 'call '+script_name

            if len(script)==0:
                script.append('@echo off')
                script.append('')
        else:
            xcmd = 'chmod 755 '+script_name+' ; ./'+script_name

            if len(script)==0:
                script.append('#!/bin/bash')
                script.append('')

        # Assemble env
        if len(env)>0:
            for k in env:
                v=env[k]

                if os.name == 'nt':
                    script.append('set '+k+'='+v)
                else:
                    if ' ' in v: v='"'+v+'"'
                    script.append('export '+k+'='+v)

            script.append('')

        # Add CMD        
        script.append(cmd)

        # Record script
        r = utils.save_txt(file_name=script_name, string='\n'.join(script))
        if r['return']>0: return r

        # Run script
        rc = os.system(xcmd)

        return {'return':0, 'return_code':rc}

    def add(self, i):
        """
        Add CM script

        Args:
          (CM input dict): 

          (out) (str): if 'con', output to console

          parsed_artifact (list): prepared in CM CLI or CM access function
                                    [ (artifact alias, artifact UID) ] or
                                    [ (artifact alias, artifact UID), (artifact repo alias, artifact repo UID) ]

          (tags) (str): tags to find an CM script (CM artifact)

          (script_name) (str): name of script (it will be copied to the new entry and added to the meta)

          (tags) (string or list): tags to be added to meta

          (new_tags) (string or list): new tags to be added to meta (the same as tags)

          (json) (bool): if True, record JSON meta instead of YAML

          (meta) (dict): preloaded meta

          (template) (string): template to use (python)
          (python) (bool): template=python
          (pytorch) (bool): template=pytorch
          ...

        Returns:
          (CM return dict):

          * return (int): return code == 0 if no error and >0 if error

        """
        import shutil

        console = i.get('out') == 'con'

        # Try to find script artifact by alias and/or tags
        ii = utils.sub_input(i, self.cmind.cfg['artifact_keys'])

        parsed_artifact = i.get('parsed_artifact',[])

        artifact_obj = parsed_artifact[0] if len(parsed_artifact)>0 else None
        artifact_repo = parsed_artifact[1] if len(parsed_artifact)>1 else None

        script_name = ''
        if 'script_name' in i:
           script_name = i.get('script_name','').strip()
           del(i['script_name'])

           if script_name != '' and not os.path.isfile(script_name):
               return {'return':1, 'error':'file {} not found'.format(script_name)}

        # Move tags from input to meta of the newly created script artifact
        tags_list = utils.convert_tags_to_list(i)
        if 'tags' in i: del(i['tags'])

        if len(tags_list)==0:
            if console:
                x=input('Please specify a combination of unique tags separated by comma for this script: ')
                x = x.strip()
                if x!='':
                    tags_list = x.split(',')

        if len(tags_list)==0:
            return {'return':1, 'error':'you must specify a combination of unique tags separate by comman using "--new_tags"'}

        # Add placeholder (use common action)
        ii['out']='con'
        ii['common']=True # Avoid recursion - use internal CM add function to add the script artifact

        # Check template path
        template_dir = 'template'

        template = i.get('template','')

        if template == '':
           if i.get('python', False):
               template = 'python'
           elif i.get('pytorch', False):
               template = 'pytorch'

        if template!='':
            template_dir += '-'+template

        template_path = os.path.join(self.path, template_dir)

        if not os.path.isdir(template_path):
            return {'return':1, 'error':'template path {} not found'.format(template_path)}

        # Check if preloaded meta exists
        meta = {
                 'cache':False
# 20240127: Grigori commented that because newly created script meta looks ugly
#                 'new_env_keys':[],
#                 'new_state_keys':[],
#                 'input_mapping':{},
#                 'docker_input_mapping':{},
#                 'deps':[],
#                 'prehook_deps':[],
#                 'posthook_deps':[],
#                 'post_deps':[],
#                 'versions':{},
#                 'variations':{},
#                 'input_description':{}
               }

        fmeta = os.path.join(template_path, self.cmind.cfg['file_cmeta'])

        r = utils.load_yaml_and_json(fmeta)
        if r['return']==0:
            utils.merge_dicts({'dict1':meta, 'dict2':r['meta'], 'append_lists':True, 'append_unique':True})

        # Check meta from CMD
        xmeta = i.get('meta',{})

        if len(xmeta)>0:
            utils.merge_dicts({'dict1':meta, 'dict2':xmeta, 'append_lists':True, 'append_unique':True})

        meta['automation_alias']=self.meta['alias']
        meta['automation_uid']=self.meta['uid']
        meta['tags']=tags_list

        script_name_base = script_name
        script_name_ext = ''
        if script_name!='':
            # separate name and extension
            j=script_name.rfind('.')
            if j>=0:
                script_name_base = script_name[:j]
                script_name_ext = script_name[j:]

            meta['script_name'] = script_name_base

        ii['meta']=meta
        ii['action']='add'

        use_yaml = True if not i.get('json',False) else False

        if use_yaml:
            ii['yaml']=True

        ii['automation']='script,5b4e0237da074764'

        for k in ['parsed_automation', 'parsed_artifact']:
            if k in ii: del ii[k]

        if artifact_repo != None:
            artifact = ii.get('artifact','')
            ii['artifact'] = utils.assemble_cm_object2(artifact_repo) + ':' + artifact

        r_obj=self.cmind.access(ii)
        if r_obj['return']>0: return r_obj

        new_script_path = r_obj['path']

        if console:
            logging.info('Created script in {}'.format(new_script_path))

        # Copy files from template (only if exist)
        files = [
                 (template_path, 'README-extra.md', ''),
                 (template_path, 'customize.py', ''),
                 (template_path, 'main.py', ''),
                 (template_path, 'requirements.txt', ''),
                 (template_path, 'install_deps.bat', ''),
                 (template_path, 'install_deps.sh', ''),
                 (template_path, 'plot.bat', ''),
                 (template_path, 'plot.sh', ''),
                 (template_path, 'analyze.bat', ''),
                 (template_path, 'analyze.sh', ''),
                 (template_path, 'validate.bat', ''),
                 (template_path, 'validate.sh', '')
                ]

        if script_name == '':
            files += [(template_path, 'run.bat', ''),
                      (template_path, 'run.sh',  '')]
        else:
            if script_name_ext == '.bat':
                files += [(template_path, 'run.sh', script_name_base+'.sh')]
                files += [('', script_name, script_name)]

            else:
                files += [(template_path, 'run.bat', script_name_base+'.bat')]
                files += [('', script_name, script_name_base+'.sh')]


        for x in files:
            path = x[0]
            f1 = x[1]
            f2 = x[2]

            if f2 == '':
                f2 = f1

            if path!='':
                f1 = os.path.join(path, f1)

            if os.path.isfile(f1):
                f2 = os.path.join(new_script_path, f2)

                if console:
                    logging.info('  * Copying {} to {}'.format(f1, f2))

                shutil.copyfile(f1,f2)

        return r_obj

    def _get_name_for_dynamic_variation_tag(script, variation_tag):
        '''
        Returns the variation name in meta for the dynamic_variation_tag
        '''
        if "." not in variation_tag or variation_tag[-1] == ".":
            return None
        return variation_tag[:variation_tag.index(".")+1]+"#"


    def _update_variation_meta_with_dynamic_suffix(script, variation_meta, variation_tag_dynamic_suffix):
        '''
        Updates the variation meta with dynamic suffix
        '''
        for key in variation_meta:
            value = variation_meta[key]

            if type(value) is list: #deps,pre_deps...
                for item in value:
                    if type(item) is dict:
                        for item_key in item:
                            item_value = item[item_key]
                            if type(item_value) is dict: #env,default_env inside deps
                                for item_key2 in item_value:
                                    item_value[item_key2] = item_value[item_key2].replace("#", variation_tag_dynamic_suffix)
                            elif type(item_value) is list: #names for example
                                for i,l_item in enumerate(item_value):
                                    if type(l_item) is str:
                                        item_value[i] = l_item.replace("#", variation_tag_dynamic_suffix)
                            else:
                                item[item_key] = item[item_key].replace("#", variation_tag_dynamic_suffix)

            elif type(value) is dict: #add_deps, env, ..
                for item in value:
                    item_value = value[item]
                    if type(item_value) is dict: #deps
                        for item_key in item_value:
                            item_value2 = item_value[item_key]
                            if type(item_value2) is dict: #env,default_env inside deps
                                for item_key2 in item_value2:
                                    item_value2[item_key2] = item_value2[item_key2].replace("#", variation_tag_dynamic_suffix)
                            else:
                                item_value[item_key] = item_value[item_key].replace("#", variation_tag_dynamic_suffix)
                    else:
                        if type(item_value) is list: # lists inside env...
                            for i,l_item in enumerate(item_value):
                                if type(l_item) is str:
                                    item_value[i] = l_item.replace("#", variation_tag_dynamic_suffix)
                        else:
                            value[item] = value[item].replace("#", variation_tag_dynamic_suffix)

            else: #scalar value
                pass #no dynamic update for now

    def _get_variations_with_aliases(script, variation_tags, variations):
        '''
        Automatically turn on variation tags which are aliased by any given tag
        '''
        import copy
        tmp_variation_tags=copy.deepcopy(variation_tags)

        excluded_variations = [ k[1:] for k in variation_tags if k.startswith("-") ]
        for i,e in enumerate(excluded_variations):
            if e not in variations:
                dynamic_tag = script._get_name_for_dynamic_variation_tag(e)
                if dynamic_tag and dynamic_tag in variations:
                    excluded_variations[i] = dynamic_tag

        for k in variation_tags:
            if k.startswith("-"):
                continue
            if k in variations:
                variation = variations[k]
            else:
                variation = variations[script._get_name_for_dynamic_variation_tag(k)]
            if 'alias' in variation:

                if variation['alias'] in excluded_variations:
                    return {'return': 1, 'error': 'Alias "{}" specified for the variation "{}" is conflicting with the excluded variation "-{}" '.format(variation['alias'], k, variation['alias'])}

                if variation['alias'] not in variations:
                    return {'return': 1, 'error': 'Alias "{}" specified for the variation "{}" is not existing '.format(variation['alias'], k)}

                if 'group' in variation:
                    return {'return': 1, 'error': 'Incompatible combinations: (alias, group) specified for the variation "{}" '.format(k)}

                if 'default' in variation:
                    return {'return': 1, 'error': 'Incompatible combinations: (default, group) specified for the variation "{}" '.format(k)}

                if variation['alias'] not in tmp_variation_tags:
                    tmp_variation_tags.append(variation['alias'])

        return {'return':0, 'variation_tags': tmp_variation_tags, 'excluded_variation_tags': excluded_variations}

    def _get_variation_groups(script, variations):
        groups = {}

        for k in variations:
            variation = variations[k]
            if not variation:
                continue
            if 'group' in variation:
                if variation['group'] not in groups:
                    groups[variation['group']] = {}
                    groups[variation['group']]['variations'] = []
                groups[variation['group']]['variations'].append(k)
                if 'default' in variation:
                    if 'default' in groups[variation['group']]:
                        return {'return': 1, 'error': 'Multiple defaults specied for the variation group "{}": "{},{}" '.format(variation['group'], k, groups[variation['group']]['default'])}
                    groups[variation['group']]['default'] = k

        return {'return': 0, 'variation_groups': groups}

    def _process_variation_tags_in_groups(script, variation_tags, groups, excluded_variations, variations):
        import copy
        tmp_variation_tags = copy.deepcopy(variation_tags)
        tmp_variation_tags_static = copy.deepcopy(variation_tags)

        for v_i in range(len(tmp_variation_tags_static)):
            v = tmp_variation_tags_static[v_i]

            if v not in variations:
                v_static = script._get_name_for_dynamic_variation_tag(v)
                tmp_variation_tags_static[v_i] = v_static

        for k in groups:
            group = groups[k]
            unique_allowed_variations = group['variations']

            if len(set(unique_allowed_variations) & set(tmp_variation_tags_static)) > 1:
                return {'return': 1, 'error': 'Multiple variation tags selected for the variation group "{}": {} '.format(k, str(set(unique_allowed_variations) & set(tmp_variation_tags_static)))}
            if len(set(unique_allowed_variations) & set(tmp_variation_tags_static)) == 0:
                if 'default' in group and group['default'] not in excluded_variations:
                    tmp_variation_tags.append(group['default'])

        return {'return':0, 'variation_tags': tmp_variation_tags}

    def _call_run_deps(script, deps, local_env_keys, local_env_keys_from_meta, env, state, const, const_state,
            add_deps_recursive, recursion_spaces, remembered_selections, variation_tags_string, found_cached, debug_script_tags='', 
            verbose=False, show_time=False, extra_recursion_spaces='  ', run_state={'deps':[], 'fake_deps':[], 'parent': None}):
        if len(deps) == 0:
            return {'return': 0}

        # Check chain of post hook dependencies on other CM scripts
        import copy

        # Get local env keys
        local_env_keys = copy.deepcopy(local_env_keys)

        if len(local_env_keys_from_meta)>0:
            local_env_keys += local_env_keys_from_meta

        r = script._run_deps(deps, local_env_keys, env, state, const, const_state, add_deps_recursive, recursion_spaces,
            remembered_selections, variation_tags_string, found_cached, debug_script_tags, 
            verbose, show_time, extra_recursion_spaces, run_state)
        if r['return']>0: return r

        return {'return': 0}

    def _run_deps(self, deps, clean_env_keys_deps, env, state, const, const_state, add_deps_recursive, recursion_spaces, 
                    remembered_selections, variation_tags_string='', from_cache=False, debug_script_tags='', 
                  verbose=False, show_time=False, extra_recursion_spaces='  ', run_state={'deps':[], 'fake_deps':[], 'parent': None}):
        """
        Runs all the enabled dependencies and pass them env minus local env
        """

        if len(deps)>0:
            # Preserve local env
            tmp_env = {}

            variation_groups = run_state.get('variation_groups')

            for d in deps:

                if not d.get('tags'):
                    continue

                if d.get('skip_if_fake_run', False) and env.get('CM_TMP_FAKE_RUN','')=='yes':
                    continue
                
                if "enable_if_env" in d:
                    if not enable_or_skip_script(d["enable_if_env"], env):
                        continue

                if "enable_if_any_env" in d:
                    if not any_enable_or_skip_script(d["enable_if_any_env"], env):
                        continue

                if "skip_if_env" in d:
                    if enable_or_skip_script(d["skip_if_env"], env):
                        continue

                if "skip_if_any_env" in d:
                    x = any_enable_or_skip_script(d["skip_if_any_env"], env)
                    if x:
                        continue

                if from_cache and not d.get("dynamic", None):
                    continue

                update_tags_from_env_with_prefix = d.get("update_tags_from_env_with_prefix", {})
                for t in update_tags_from_env_with_prefix:
                    for key in update_tags_from_env_with_prefix[t]:
                        if str(env.get(key, '')).strip() != '':
                            d['tags']+=","+t+str(env[key])

                for key in clean_env_keys_deps:
                    if '?' in key or '*' in key:
                        import fnmatch
                        for kk in list(env.keys()):
                            if fnmatch.fnmatch(kk, key):
                                tmp_env[kk] = env[kk]
                                del(env[kk])
                    elif key in env:
                        tmp_env[key] = env[key]
                        del(env[key])

                import re
                for key in list(env.keys()):
                    value = env[key]
                    tmp_values = re.findall(r'<<<(.*?)>>>', str(value))
                    if tmp_values == []: continue
                    tmp_env[key] = env[key]
                    del(env[key])

                force_env_keys_deps = d.get("force_env_keys", [])
                for key in force_env_keys_deps:
                    if '?' in key or '*' in key:
                        import fnmatch
                        for kk in list(tmp_env.keys()):
                            if fnmatch.fnmatch(kk, key):
                                env[kk] = tmp_env[kk]
                    elif key in tmp_env:
                        env[key] = tmp_env[key]

                if d.get("reuse_version", False):
                    for k in tmp_env:
                        if k.startswith('CM_VERSION'):
                            env[k] = tmp_env[k]

                update_tags_from_env = d.get("update_tags_from_env", [])
                for t in update_tags_from_env:
                    if env.get(t, '').strip() != '':
                        d['tags']+=","+env[t]

                inherit_variation_tags = d.get("inherit_variation_tags", False)
                skip_inherit_variation_groups = d.get("skip_inherit_variation_groups", [])
                variation_tags_to_be_skipped = []
                if inherit_variation_tags:
                    if skip_inherit_variation_groups: #skips inheriting variations belonging to given groups
                        for group in variation_groups:
                            if group in skip_inherit_variation_groups:
                                variation_tags_to_be_skipped += variation_groups[group]['variations']

                    variation_tags = variation_tags_string.split(",")
                    variation_tags =  [ x for x in variation_tags if not x.startswith("_") or x[1:] not in set(variation_tags_to_be_skipped) ]

                    # handle group in case of dynamic variations
                    for t_variation in variation_tags_to_be_skipped:
                        if t_variation.endswith(".#"):
                            beg = t_variation[:-1]
                            for m_tag in variation_tags:
                                if m_tag.startswith("_"+beg):
                                    variation_tags.remove(m_tag)

                    deps_tags = d['tags'].split(",")
                    for tag in deps_tags:
                        if tag.startswith("-_") or tag.startswith("_-"):
                            variation_tag = "_" + tag[2:]
                            if variation_tag in variation_tags:
                                variation_tags.remove(variation_tag)
                    new_variation_tags_string = ",".join(variation_tags)
                    d['tags']+=","+new_variation_tags_string #deps should have non-empty tags

                run_state['deps'].append(d['tags'])

                if not run_state['fake_deps']:
                    import copy
                    tmp_run_state_deps = copy.deepcopy(run_state['deps'])
                    run_state['deps'] = []
                    tmp_parent = run_state['parent']

                    run_state['parent'] = run_state['script_id']

                    if len(run_state['script_variation_tags']) > 0:
                        run_state['parent'] += " ( " + ',_'.join(run_state['script_variation_tags']) + " )"

                    tmp_script_id = run_state['script_id']
                    tmp_script_variation_tags = run_state['script_variation_tags']

                    # Run collective script via CM API:
                    # Not very efficient but allows logging - can be optimized later

                    ii = {
                            'action':'run',
                            'automation':utils.assemble_cm_object(self.meta['alias'], self.meta['uid']),
                            'recursion_spaces':recursion_spaces, # + extra_recursion_spaces,
                            'recursion':True,
                            'remembered_selections': remembered_selections,
                            'env':env,
                            'state':state,
                            'const':const,
                            'const_state':const_state,
                            'add_deps_recursive':add_deps_recursive,
                            'debug_script_tags':debug_script_tags,
                            'verbose':verbose,
                            'silent':run_state.get('tmp_silent', False),
                            'time':show_time,
                            'run_state':run_state

                        }

                    for key in [ "env", "state", "const", "const_state" ]:
                        ii['local_'+key] = d.get(key, {})
                        if d.get(key):
                            d[key] = {}

                    utils.merge_dicts({'dict1':ii, 'dict2':d, 'append_lists':True, 'append_unique':True})

                    r = update_env_with_values(ii['env']) #to update env local to a dependency
                    if r['return']>0: return r 

                    r = self.cmind.access(ii)
                    if r['return']>0: return r

                    run_state['deps'] = tmp_run_state_deps
                    run_state['parent'] = tmp_parent
                    run_state['script_id'] = tmp_script_id
                    run_state['script_variation_tags'] = tmp_script_variation_tags

                    # Restore local env
                    env.update(tmp_env)
                    r = update_env_with_values(env)
                    if r['return']>0: return r 

        return {'return': 0}

    def _merge_dicts_with_tags(self, dict1, dict2):
        """
        Merges two dictionaries and append any tag strings in them
        """
        if dict1 == dict2:
            return {'return': 0}
        for dep in dict1:
            if 'tags' in dict1[dep]:
                dict1[dep]['tags_list'] = utils.convert_tags_to_list(dict1[dep])
        for dep in dict2:
            if 'tags' in dict2:
                dict2[dep]['tags_list'] = utils.convert_tags_to_list(dict2[dep])
        utils.merge_dicts({'dict1':dict1, 'dict2':dict2, 'append_lists':True, 'append_unique':True})
        for dep in dict1:
            if 'tags_list' in dict1[dep]:
                dict1[dep]['tags'] = ",".join(dict1[dep]['tags_list'])
                del(dict1[dep]['tags_list'])
        for dep in dict2:
            if 'tags_list' in dict2[dep]:
                del(dict2[dep]['tags_list'])

    def _get_readme(self, cmd_parts, run_state):
        """
        Outputs a Markdown README file listing the CM run commands for the dependencies
        """

        deps = run_state['deps']

        version_info = run_state.get('version_info', [])
        version_info_dict = {}

        for v in version_info:
            k = list(v.keys())[0]
            version_info_dict[k]=v[k]

        content = ''

        content += """
*This README was automatically generated by the [CM framework](https://github.com/mlcommons/ck).*

## Install CM

```bash
pip install cmind -U
Check this readme
with more details about installing CM and dependencies across different platforms
(Ubuntu, MacOS, Windows, RHEL, ...).

Install CM automation repositories
bash
Copy code
cm pull repo mlcommons@cm4mlops --checkout=dev
"""

        current_cm_repo = run_state['script_repo_alias']
        if current_cm_repo not in ['mlcommons@ck', 'mlcommons@cm4mlops']:
            content += '\ncm pull repo ' + run_state['script_repo_alias'] + '\n'

        content += """```

## Run CM script

```bash
"""

        cmd="cm run script "

        for cmd_part in cmd_parts:
            x = '"' if ' ' in cmd_part and not cmd_part.startswith('-') else ''
            cmd = cmd + " " + x + cmd_part + x

        content += cmd + '\n'

        content += """```

## Run individual CM scripts to customize dependencies (optional)

"""
        deps_ = ''

        for dep_tags in deps:

            xversion = ''
            version = version_info_dict.get(dep_tags, {}).get('version','')
            if version !='' :
                xversion = ' --version={}\n'.format(version)

            content += "```bash\n"
            content += "cm run script --tags=" + dep_tags + "{}\n".format(xversion)
            content += "```\n\n"

        return content

    def _get_docker_container(self, cmd_parts, run_state):
        """
        Outputs a Markdown README file listing the CM run commands for the dependencies
        """

        deps = run_state['deps']

        version_info = run_state.get('version_info', [])
        version_info_dict = {}

        for v in version_info:
            k = list(v.keys())[0]
            version_info_dict[k]=v[k]

        content = ''

        content += """

# The following CM commands were automatically generated (prototype)

cm pull repo mlcommons@cm4mlops --checkout=dev

"""
        current_cm_repo = run_state['script_repo_alias']
        if current_cm_repo not in ['mlcommons@ck', 'mlcommons@cm4mlops']:
            content += '\ncm pull repo ' + run_state['script_repo_alias'] + '\n\n'


        deps_ = ''

        for dep_tags in deps:

            xversion = ''
            version = version_info_dict.get(dep_tags, {}).get('version','')
            if version !='' :
                xversion = ' --version={}\n'.format(version)

            content += "# cm run script --tags=" + dep_tags + "{}\n\n".format(xversion)

        cmd="cm run script "

        for cmd_part in cmd_parts:
            x = '"' if ' ' in cmd_part and not cmd_part.startswith('-') else ''
            cmd = cmd + " " + x + cmd_part + x

        content += cmd + '\n'


        return content

    def _print_versions(self, run_state):
        """
        Print versions in the nice format
        """

        version_info = run_state.get('version_info', [])

        logging.info('=========================')
        logging.info('Versions of dependencies:')
        logging.info('')

        for v in version_info:
            k = list(v.keys())[0]
            version_info_dict=v[k]

            version = version_info_dict.get('version','')

            if version !='' :
                logging.info('* {}: {}'.format(k, version))

        logging.info('=========================')

        return {}

    def _markdown_cmd(self, cmd):
        """
        Returns a CM command in markdown format
        """

        return '```bash\n '+cmd+' \n ```'

    def _print_deps(self, deps):
        """
        Prints the CM run commands for the list of CM script dependencies
        """

        print_deps_data = []
        run_cmds = self._get_deps_run_cmds(deps)

        logging.info('')
        for cmd in run_cmds:
            print_deps_data.append(cmd)
            logging.info(cmd)

        return print_deps_data

    def _get_deps_run_cmds(self, deps):
        """
        Returns the CM run commands for the list of CM script dependencies
        """

        run_cmds = []

        for dep_tags in deps:
            run_cmds.append("cm run script --tags="+dep_tags)

        return run_cmds

    def run_native_script(self, i):
        """
        Run native script in a CM script entry
        (wrapper around "prepare_and_run_script_with_postprocessing" function)

        Args:
          (dict):

            run_script_input (dict): saved input for "prepare_and_run_script_with_postprocessing" function
            env (dict): the latest environment for the script
            script_name (str): native script name

        Returns:
          (dict): Output from "prepare_and_run_script_with_postprocessing" function
        """

        import copy

        run_script_input = i['run_script_input']
        script_name = i['script_name']
        env = i.get('env','')

        # Create and work on a copy to avoid contamination
        env_copy = copy.deepcopy(run_script_input.get('env',{}))
        run_script_input_state_copy = copy.deepcopy(run_script_input.get('state',{}))
        script_name_copy = run_script_input.get('script_name','')

        run_script_input['script_name'] = script_name
        run_script_input['env'] = env

        r = prepare_and_run_script_with_postprocessing(run_script_input, postprocess="")

        env_tmp = copy.deepcopy(run_script_input['env'])
        r['env_tmp'] = env_tmp

        run_script_input['state'] = run_script_input_state_copy
        run_script_input['env'] = env_copy
        run_script_input['script_name'] = script_name_copy

        return r

    def find_file_in_paths(self, i):
        """
        Find file name in a list of paths

        Args:
          (CM input dict):

          paths (list): list of paths
          file_name (str): filename pattern to find
          (select) (bool): if True and more than 1 path found, select
          (select_default) (bool): if True, select the default one
          (recursion_spaces) (str): add space to print
          (run_script_input) (dict): prepared dict to run script and detect version

          (detect_version) (bool): if True, attempt to detect version
          (env_path) (str): env key to pass path to the script to detect version
          (run_script_input) (dict): use this input to run script to detect version
          (env) (dict): env to check/force version

          (hook) (func): call this func to skip some artifacts

        Returns:
           (CM return dict):

           * return (int): return code == 0 if no error and >0 if error
           * (error) (str): error string if return>0

           (found_files) (list): paths to files when found
        """
        import copy

        paths = i['paths']
        select = i.get('select',False)
        select_default = i.get('select_default', False)
        recursion_spaces = i.get('recursion_spaces','')

        hook = i.get('hook', None)

        verbose = i.get('verbose', False)
        if not verbose: verbose = i.get('v', False)

        file_name = i.get('file_name', '')
        file_name_re = i.get('file_name_re', '')
        file_is_re = False

        if file_name_re != '':
            file_name = file_name_re
            file_is_re = True

        if file_name == '':
            raise Exception('file_name or file_name_re not specified in find_artifact')

        found_files = []

        import glob
        import re

        for path in paths:
            # May happen that path is in variable but it doesn't exist anymore
            if os.path.isdir(path):
                if file_is_re:
                    file_list = [os.path.join(path,f)  for f in os.listdir(path) if re.match(file_name, f)]

                    for f in file_list:
                        duplicate = False
                        for existing in found_files:
                            if os.path.samefile(existing, f):
                                duplicate = True
                                break
                        if not duplicate:
                            skip = False
                            if hook!=None:
                               r=hook({'file':f})
                               if r['return']>0: return r
                               skip = r['skip']
                            if not skip:
                                found_files.append(f)

                else:
                    path_to_file = os.path.join(path, file_name)

                    file_pattern_suffixes = [
                            "",
                            ".[0-9]",
                            ".[0-9][0-9]",
                            "-[0-9]",
                            "-[0-9][0-9]",
                            "[0-9]",
                            "[0-9][0-9]",
                            "[0-9].[0-9]",
                            "[0-9][0][0].[0]",
                            "[0-9][0-9].[0-9][0-9]"
                            ]

                    for suff in file_pattern_suffixes:
                        file_list = glob.glob(path_to_file + suff)
                        for f in file_list:
                            duplicate = False

                            for existing in found_files:
                                try:
                                    if os.path.samefile(existing, f):
                                        duplicate = True
                                        break
                                except Exception as e:
                                    # This function fails on Windows sometimes 
                                    # because some files can't be accessed
                                    pass

                            if not duplicate:
                                skip = False
                                if hook!=None:
                                   r=hook({'file':f})
                                   if r['return']>0: return r
                                   skip = r['skip']
                                if not skip:
                                    found_files.append(f)


        if select:
            # Check and prune versions
            if i.get('detect_version', False):
                found_paths_with_good_version = []
                found_files_with_good_version = []

                env = i.get('env', {})

                run_script_input = i['run_script_input']
                env_path_key = i['env_path_key']

                version = env.get('CM_VERSION', '')
                version_min = env.get('CM_VERSION_MIN', '')
                version_max = env.get('CM_VERSION_MAX', '')

                x = ''

                if version != '': x += ' == {}'.format(version)
                if version_min != '': x += ' >= {}'.format(version_min)
                if version_max != '': x += ' <= {}'.format(version_max)

                if x!='':
                    logging.info(recursion_spaces + '  - Searching for versions: {}'.format(x))

                new_recursion_spaces = recursion_spaces + '    '

                for path_to_file in found_files:

                    logging.info('')
                    logging.info(recursion_spaces + '    * ' + path_to_file)

                    run_script_input['env'] = env
                    run_script_input['env'][env_path_key] = path_to_file
                    run_script_input['recursion_spaces'] = new_recursion_spaces

                    rx = prepare_and_run_script_with_postprocessing(run_script_input, postprocess="detect_version")

                    run_script_input['recursion_spaces'] = recursion_spaces

                    if rx['return']>0:
                       if rx['return'] != 2:
                           return rx
                    else:
                       # Version was detected
                       detected_version = rx.get('version','')

                       if detected_version != '':
                           if detected_version == -1:
                               logging.info(recursion_spaces + '    SKIPPED due to incompatibility ...')
                           else:
                               ry = check_version_constraints({'detected_version': detected_version,
                                                               'version': version,
                                                               'version_min': version_min,
                                                               'version_max': version_max,
                                                               'cmind':self.cmind})
                               if ry['return']>0: return ry

                               if not ry['skip']:
                                   found_files_with_good_version.append(path_to_file)
                               else:
                                   logging.info(recursion_spaces + '    SKIPPED due to version constraints ...')

                found_files = found_files_with_good_version

            # Continue with selection
            if len(found_files)>1:
                if len(found_files) == 1 or select_default:
                    selection = 0
                else:
                    # Select 1 and proceed
                    logging.info(recursion_spaces+'  - More than 1 path found:')

                    logging.info('')
                    num = 0

                    for file in found_files:
                        logging.info(recursion_spaces+'  {}) {}'.format(num, file))
                        num += 1

                    logging.info('')
                    x=input(recursion_spaces+'  Make your selection or press Enter for 0: ')

                    x=x.strip()
                    if x=='': x='0'

                    selection = int(x)

                    if selection < 0 or selection >= num:
                        selection = 0

                logging.info('')
                logging.info(recursion_spaces+'  Selected {}: {}'.format(selection, found_files[selection]))

                found_files = [found_files[selection]]

        return {'return':0, 'found_files':found_files}

    def detect_version_using_script(self, i):
        """
        Detect version using script

        Args:
          (CM input dict): 

          (recursion_spaces) (str): add space to print

          run_script_input (dict): use this input to run script to detect version
          (env) (dict): env to check/force version

        Returns:
           (CM return dict):

           * return (int): return code == 0 if no error and >0 if error
                                             16 if not detected
           * (error) (str): error string if return>0

           (detected_version) (str): detected version
        """
        recursion_spaces = i.get('recursion_spaces','')

        import copy

        detected = False

        env = i.get('env', {})

        run_script_input = i['run_script_input']

        version = env.get('CM_VERSION', '')
        version_min = env.get('CM_VERSION_MIN', '')
        version_max = env.get('CM_VERSION_MAX', '')

        x = ''

        if version != '': x += ' == {}'.format(version)
        if version_min != '': x += ' >= {}'.format(version_min)
        if version_max != '': x += ' <= {}'.format(version_max)

        if x!='':
            logging.info(recursion_spaces + '  - Searching for versions: {}'.format(x))

        new_recursion_spaces = recursion_spaces + '    '

        run_script_input['recursion_spaces'] = new_recursion_spaces
        run_script_input['env'] = env

        # Prepare run script
        rx = prepare_and_run_script_with_postprocessing(run_script_input, postprocess="detect_version")

        run_script_input['recursion_spaces'] = recursion_spaces

        if rx['return'] == 0: 
           # Version was detected 
           detected_version = rx.get('version','')

           if detected_version != '':
               ry = check_version_constraints({'detected_version': detected_version,
                                               'version': version,
                                               'version_min': version_min,
                                               'version_max': version_max,
                                               'cmind':self.cmind})
               if ry['return']>0: return ry

               if not ry['skip']:
                   return {'return':0, 'detected_version':detected_version}

        return {'return':16, 'error':'version was not detected'}

    def find_artifact(self, i):
        """
        Find some artifact (file) by name

        Args:
          (CM input dict): 

          file_name (str): filename to find

          env (dict): global env
          os_info (dict): OS info

          (detect_version) (bool): if True, attempt to detect version
          (env_path) (str): env key to pass path to the script to detect version
          (run_script_input) (dict): use this input to run script to detect version

          (default_path_env_key) (str): check in default paths from global env 
                                        (PATH, PYTHONPATH, LD_LIBRARY_PATH ...)

          (recursion_spaces) (str): add space to print

          (hook) (func): call this func to skip some artifacts

        Returns:
           (CM return dict):

           * return (int): return code == 0 if no error and >0 if error
           * (error) (str): error string if return>0
                            error = 16 if artifact not found but no problem

           found_path (list): found path to an artifact
           full_path (str): full path to a found artifact
           default_path_list (list): list of default paths 
        """
        import copy

        file_name = i['file_name']

        os_info = i['os_info']

        env = i['env']

        env_path_key = i.get('env_path_key', '')

        run_script_input = i.get('run_script_input', {})
        extra_paths = i.get('extra_paths', {})

        # Create and work on a copy to avoid contamination
        env_copy = copy.deepcopy(env)
        run_script_input_state_copy = copy.deepcopy(run_script_input.get('state',{}))

        default_path_env_key = i.get('default_path_env_key', '')
        recursion_spaces = i.get('recursion_spaces', '')

        hook = i.get('hook', None)

        # Check if forced to search in a specific path or multiple paths 
        # separated by OS var separator (usually : or ;)
        path = env.get('CM_TMP_PATH','')

        if path!='' and env.get('CM_TMP_PATH_IGNORE_NON_EXISTANT','')!='yes':
            # Can be a list of paths
            path_list_tmp = path.split(os_info['env_separator'])
            for path_tmp in path_list_tmp:
                if path_tmp.strip()!='' and not os.path.isdir(path_tmp):
                    return {'return':1, 'error':'path {} doesn\'t exist'.format(path_tmp)}

        # Check if forced path and file name from --input (CM_INPUT - local env - will not be visible for higher-level script)
        forced_file = env.get('CM_INPUT','').strip()
        if forced_file != '':
            if not os.path.isfile(forced_file):
                return {'return':1, 'error':'file {} doesn\'t exist'.format(forced_file)}

            file_name = os.path.basename(forced_file)
            path = os.path.dirname(forced_file)

        default_path_list = self.get_default_path_list(i)
        #[] if default_path_env_key == '' else \
        #   os.environ.get(default_path_env_key,'').split(os_info['env_separator'])


        if path == '':
            path_list_tmp = default_path_list
        else:
            logging.info(recursion_spaces + '    # Requested paths: {}'.format(path))
            path_list_tmp = path.split(os_info['env_separator'])

        # Check soft links
        path_list_tmp2 = []
        for path_tmp in path_list_tmp:
#            path_tmp_abs = os.path.realpath(os.path.join(path_tmp, file_name))
#            GF: I remarked above code because it doesn't work correcly
#                for virtual python - it unsoftlinks virtual python and picks up
#                native one from /usr/bin thus making workflows work incorrectly ...
            path_tmp_abs = os.path.join(path_tmp, file_name)

            if not path_tmp_abs in path_list_tmp2:
                path_list_tmp2.append(path_tmp_abs)

        path_list = []
        for path_tmp in path_list_tmp2:
            path_list.append(os.path.dirname(path_tmp))

        # Check if quiet
        select_default = True if env.get('CM_QUIET','') == 'yes' else False

        # Prepare paths to search
        r = self.find_file_in_paths({'paths': path_list,
                                     'file_name': file_name, 
                                     'select': True,
                                     'select_default': select_default,
                                     'detect_version': i.get('detect_version', False),
                                     'env_path_key': env_path_key,
                                     'env':env_copy,
                                     'hook':hook,
                                     'run_script_input': run_script_input,
                                     'recursion_spaces': recursion_spaces})

        run_script_input['state'] = run_script_input_state_copy

        if r['return']>0: return r

        found_files = r['found_files']

        if len(found_files)==0:
            return {'return':16, 'error':'{} not found'.format(file_name)}

        # Finalize output
        file_path = found_files[0]
        found_path = os.path.dirname(file_path)

        if found_path not in default_path_list:
            env_key = '+'+default_path_env_key

            paths = env.get(env_key, [])
            if found_path not in paths:
                paths.insert(0, found_path)
                env[env_key] = paths
            for extra_path in extra_paths:
                epath = os.path.normpath(os.path.join(found_path, "..", extra_path))
                if os.path.exists(epath):
                    if extra_paths[extra_path] not in env:
                        env[extra_paths[extra_path]] = []
                    env[extra_paths[extra_path]].append(epath)
        logging.info()
        logging.info(recursion_spaces + '    # Found artifact in {}'.format(file_path))

        if env_path_key != '':
            env[env_path_key] = file_path

        return {'return':0, 'found_path':found_path, 
                            'found_file_path':file_path,
                            'found_file_name':os.path.basename(file_path),
                            'default_path_list': default_path_list}

    def find_file_deep(self, i):
        """
        Find file name in a list of paths

        Args:
          (CM input dict):

            paths (list): list of paths
            file_name (str): filename pattern to find
            (restrict_paths) (list): restrict found paths to these combinations

        Returns:
           (CM return dict):

           * return (int): return code == 0 if no error and >0 if error
           * (error) (str): error string if return>0

           (found_paths) (list): paths to files when found
        """
        paths = i['paths']
        file_name = i['file_name']

        restrict_paths = i.get('restrict_paths',[])

        found_paths = []

        for p in paths:
            if os.path.isdir(p):
                p1 = os.listdir(p)
                for f in p1:
                    p2 = os.path.join(p, f)

                    if os.path.isdir(p2):
                       r = self.find_file_deep({'paths':[p2], 'file_name': file_name, 'restrict_paths':restrict_paths})
                       if r['return']>0: return r

                       found_paths += r['found_paths']
                    else:
                       if f == file_name:
                           found_paths.append(p)
                           break

        if len(found_paths) > 0 and len(restrict_paths) > 0:
            filtered_found_paths = []

            for p in found_paths:
                for f in restrict_paths:
                    if f in p:
                        filtered_found_paths.append(p)
                        break

            found_paths = filtered_found_paths

        return {'return':0, 'found_paths':found_paths}

    def find_file_back(self, i):
        """
        Find file name backwards

        Args:
          (CM input dict):

            path (str): path to start with
            file_name (str): filename or directory to find

        Returns:
           (CM return dict):

           * return (int): return code == 0 if no error and >0 if error
           * (error) (str): error string if return>0

           (found_path) (str): path if found or empty
        """
        path = i['path']
        file_name = i['file_name']

        found_path = ''

        while path != '':
            path_to_file = os.path.join(path, file_name)
            if os.path.isfile(path_to_file):
                break

            path2 = os.path.dirname(path)

            if path2 == path:
                path = ''
                break
            else:
                path = path2

        return {'return':0, 'found_path':path}

    def parse_version(self, i):
        """
        Parse version (used in post processing functions)

        Args:
          (CM input dict): 

            (file_name) (str): filename to get version from (tmp-ver.out by default)
            match_text (str): RE match text string
            group_number (int): RE group number to get version from
            env_key (str): which env key to update
            which_env (dict): which env to update
            (debug) (boolean): if True, print some debug info

        Returns:
           (CM return dict):

           * return (int): return code == 0 if no error and >0 if error
           * (error) (str): error string if return>0

           version (str): detected version
           string (str): full file string
        """
        file_name = i.get('file_name','')
        if file_name == '': file_name = self.tmp_file_ver

        match_text = i['match_text']
        group_number = i['group_number']
        env_key = i['env_key']
        which_env = i['which_env']
        debug = i.get('debug', False)

        r = utils.load_txt(file_name = file_name,
                           check_if_exists = True, 
                           split = True,
                           match_text = match_text,
                           fail_if_no_match = 'version was not detected')
        if r['return']>0: 
           if r.get('string','')!='':
              r['error'] += ' ({})'.format(r['string'])
           return r

        string = r['string']

        version = r['match'].group(group_number)

        which_env[env_key] = version
        which_env['CM_DETECTED_VERSION'] = version # to be recorded in the cache meta

        return {'return':0, 'version':version, 'string':string}

    def update_deps(self, i):
        """
        Update deps from pre/post processing
        Args:
          (CM input dict):
          deps (dict): deps dict
          update_deps (dict): key matches "names" in deps
        Returns:
           (CM return dict):
           * return (int): return code == 0 if no error and >0 if error
           * (error) (str): error string if return>0
        """
        deps = i['deps']
        add_deps = i['update_deps']
        update_deps(deps, add_deps, False)

        return {'return':0}

    def get_default_path_list(self, i):
        default_path_env_key = i.get('default_path_env_key', '')
        os_info = i['os_info']
        default_path_list = [] if default_path_env_key == '' else \
        os.environ.get(default_path_env_key,'').split(os_info['env_separator'])

        return default_path_list

    def doc(self, i):
        """
        Document CM script.

        Args:
          (CM input dict): 

          (out) (str): if 'con', output to console

          parsed_artifact (list): prepared in CM CLI or CM access function
                                    [ (artifact alias, artifact UID) ] or
                                    [ (artifact alias, artifact UID), (artifact repo alias, artifact repo UID) ]

          (repos) (str): list of repositories to search for automations

          (output_dir) (str): output directory (../docs by default)

        Returns:
          (CM return dict):

          * return (int): return code == 0 if no error and >0 if error
          * (error) (str): error string if return>0
        """
        return utils.call_internal_module(self, __file__, 'module_misc', 'doc', i)

    def gui(self, i):
        """
        Run GUI for CM script.

        Args:
          (CM input dict):

        Returns:
          (CM return dict):

          * return (int): return code == 0 if no error and >0 if error
          * (error) (str): error string if return>0
        """
        artifact = i.get('artifact', '')
        tags = ''
        if artifact != '':
            if ' ' in artifact:
                tags = artifact.replace(' ',',')
             
        if tags=='':
            tags = i.get('tags','')

        if 'tags' in i:
            del(i['tags'])

        i['action']='run'
        i['artifact']='gui'
        i['parsed_artifact']=[('gui','605cac42514a4c69')]
        i['script']=tags.replace(',',' ')

        return self.cmind.access(i)

    def dockerfile(self, i):
        """
        Generate Dockerfile for CM script.

        Args:
          (CM input dict):

          (out) (str): if 'con', output to console

          parsed_artifact (list): prepared in CM CLI or CM access function
                                    [ (artifact alias, artifact UID) ] or
                                    [ (artifact alias, artifact UID), (artifact repo alias, artifact repo UID) ]

          (repos) (str): list of repositories to search for automations

          (output_dir) (str): output directory (./ by default)

        Returns:
          (CM return dict):

          * return (int): return code == 0 if no error and >0 if error
          * (error) (str): error string if return>0
        """
        return utils.call_internal_module(self, __file__, 'module_misc', 'dockerfile', i)

    def docker(self, i):
        """
        Run CM script in an automatically-generated container.

        Args:
          (CM input dict):

          (out) (str): if 'con', output to console

          parsed_artifact (list): prepared in CM CLI or CM access function
                                    [ (artifact alias, artifact UID) ] or
                                    [ (artifact alias, artifact UID), (artifact repo alias, artifact repo UID) ]

          (repos) (str): list of repositories to search for automations

          (output_dir) (str): output directory (./ by default)

        Returns:
          (CM return dict):

          * return (int): return code == 0 if no error and >0 if error
          * (error) (str): error string if return>0
        """
        return utils.call_internal_module(self, __file__, 'module_misc', 'docker', i)

    def _available_variations(self, i):
        """
        return error with available variations

        Args:
          (CM input dict): 

          meta (dict): meta of the script

        Returns:
           (CM return dict):

           * return (int): return code == 0 if no error and >0 if error
                                             16 if not detected
           * (error) (str): error string if return>0
        """
        meta = i['meta']

        list_of_variations = sorted(['_'+v for v in list(meta.get('variations',{}.keys()))])

        return {'return':1, 'error':'python package variation is not defined in "{}". Available: {}'.format(meta['alias'],' '.join(list_of_variations))}

    def prepare(self, i):
        """
        Run CM script with --fake_run only to resolve deps
        """
        i['fake_run']=True

        return self.run(i)

    # Reusable blocks for some scripts
    def clean_some_tmp_files(self, i):
        """
        Clean tmp files
        """
        env = i.get('env',{})

        cur_work_dir = env.get('CM_TMP_CURRENT_SCRIPT_WORK_PATH','')
        if cur_work_dir !='' and os.path.isdir(cur_work_dir):
           for x in ['tmp-run.bat', 'tmp-state.json']:
               xx = os.path.join(cur_work_dir, x)
               if os.path.isfile(xx):
                   os.remove(xx)

        return {'return':0}

    def find_cached_script(self, i):
        """
        Internal automation function: find cached script

        Args:
          (CM input dict):

          deps (dict): deps dict
          update_deps (dict): key matches "names" in deps

        Returns:
           (CM return dict):
           * return (int): return code == 0 if no error and >0 if error
           * (error) (str): error string if return>0
        """
        import copy

        recursion_spaces = i['recursion_spaces']
        script_tags = i['script_tags']
        cached_tags = []
        found_script_tags = i['found_script_tags']
        variation_tags = i['variation_tags']
        explicit_variation_tags = i['explicit_variation_tags']
        version = i['version']
        version_min = i['version_min']
        version_max = i['version_max']
        extra_cache_tags = i['extra_cache_tags']
        new_cache_entry = i['new_cache_entry']
        meta = i['meta']
        env = i['env']
        self_obj = i['self']
        skip_remembered_selections = i['skip_remembered_selections']
        remembered_selections = i['remembered_selections']
        quiet = i['quiet']
        search_tags = ''

        verbose = i.get('verbose', False)
        if not verbose: verbose = i.get('v', False)

        found_cached_scripts = []

        if verbose:
            logging.info(recursion_spaces + '  - Checking if script execution is already cached ...')

        # Create a search query to find that we already ran this script with the same or similar input
        # It will be gradually enhanced with more "knowledge"  ...
        if len(script_tags)>0:
            for x in script_tags:
                if x not in cached_tags:
                    cached_tags.append(x)

        if len(found_script_tags)>0:
            for x in found_script_tags:
                if x not in cached_tags: 
                    cached_tags.append(x)

        explicit_cached_tags=copy.deepcopy(cached_tags)

        if len(explicit_variation_tags)>0:
            explicit_variation_tags_string = ''

            for t in explicit_variation_tags:
                if explicit_variation_tags_string != '': 
                    explicit_variation_tags_string += ','
                if t.startswith("-"):
                    x = "-_" + t[1:]
                else:
                    x = '_' + t
                explicit_variation_tags_string += x

                if x not in explicit_cached_tags: 
                    explicit_cached_tags.append(x)

            if verbose:
                logging.info(recursion_spaces+'    - Prepared explicit variations: {}'.format(explicit_variation_tags_string))
        
        if len(variation_tags)>0:
            variation_tags_string = ''

            for t in variation_tags:
                if variation_tags_string != '': 
                    variation_tags_string += ','
                if t.startswith("-"):
                    x = "-_" + t[1:]
                else:
                    x = '_' + t
                variation_tags_string += x

                if x not in cached_tags: 
                    cached_tags.append(x)

            if verbose:
                logging.info(recursion_spaces+'    - Prepared variations: {}'.format(variation_tags_string))

        # Add version
        if version !='':
            if 'version-'+version not in cached_tags: 
                cached_tags.append('version-'+version)
                explicit_cached_tags.append('version-'+version)

        # Add extra cache tags (such as "virtual" for python)
        if len(extra_cache_tags)>0:
            for t in extra_cache_tags:
                if t not in cached_tags: 
                    cached_tags.append(t)
                    explicit_cached_tags.append(t)

        # Add tags from deps (will be also duplicated when creating new cache entry)
        extra_cache_tags_from_env = meta.get('extra_cache_tags_from_env',[])
        for extra_cache_tags in extra_cache_tags_from_env:
            key = extra_cache_tags['env']
            prefix = extra_cache_tags.get('prefix','')

            v = env.get(key,'').strip()
            if v!='':
                for t in v.split(','):
                    x = 'deps-' + prefix + t
                    if x not in cached_tags: 
                        cached_tags.append(x)
                        explicit_cached_tags.append(x)

        # Check if already cached
        if not new_cache_entry:
            search_tags = '-tmp'
            if len(cached_tags) >0 : 
                search_tags += ',' + ','.join(explicit_cached_tags)

            if verbose:
                logging.info(recursion_spaces+'    - Searching for cached script outputs with the following tags: {}'.format(search_tags))

            r = self_obj.cmind.access({'action':'find',
                                       'automation':self_obj.meta['deps']['cache'],
                                       'tags':search_tags})
            if r['return']>0: return r

            found_cached_scripts = r['list']

            # Check if selection is remembered
            if not skip_remembered_selections and len(found_cached_scripts) > 1:
                # Need to add extra cached tags here (since recorded later)
                for selection in remembered_selections:
                    if selection['type'] == 'cache' and set(selection['tags'].split(',')) == set(search_tags.split(',')):
                        tmp_version_in_cached_script = selection['cached_script'].meta.get('version','')

                        skip_cached_script = check_versions(self_obj.cmind, tmp_version_in_cached_script, version_min, version_max)

                        if skip_cached_script:
                            return {'return':2, 'error':'The version of the previously remembered selection for a given script ({}) mismatches the newly requested one'.format(tmp_version_in_cached_script)}
                        else:
                            found_cached_scripts = [selection['cached_script']]
                            if verbose:
                                logging.info(recursion_spaces + '  - Found remembered selection with tags "{}"!'.format(search_tags))
                            break

        if len(found_cached_scripts) > 0:
            selection = 0

            # Check version ranges ...
            new_found_cached_scripts = []

            for cached_script in found_cached_scripts:
                skip_cached_script = False
                dependent_cached_path = cached_script.meta.get('dependent_cached_path', '')
                if dependent_cached_path:
                    if not os.path.exists(dependent_cached_path):
                        #Need to rm this cache entry
                        skip_cached_script = True
                        continue

                if not skip_cached_script:
                    cached_script_version = cached_script.meta.get('version', '')

                    skip_cached_script = check_versions(self_obj.cmind, cached_script_version, version_min, version_max)

                if not skip_cached_script:
                    new_found_cached_scripts.append(cached_script)

            found_cached_scripts = new_found_cached_scripts

        return {'return':0, 'cached_tags':cached_tags, 'search_tags':search_tags, 'found_cached_scripts':found_cached_scripts}

    def enable_or_skip_script(meta, env):
        """
        Internal: enable a dependency based on enable_if_env and skip_if_env meta information
        (AND function)
        """
        for key in meta:
            if key in env:
                value = str(env[key]).lower()

                meta_key = [str(v).lower() for v in meta[key]]

                if set(meta_key) & set(["yes", "on", "true", "1"]):
                    if value not in ["no", "off", "false", "0"]:
                        continue
                elif set(meta_key) & set(["no", "off", "false", "0"]):
                    if value in ["no", "off", "false", "0"]:
                        continue
                elif value in meta_key:
                    continue
            return False

        return True

    def any_enable_or_skip_script(meta, env):
        """
        Internal: enable a dependency based on enable_if_env and skip_if_env meta information
        (OR function)
        """
        for key in meta:
            found = False
            if key in env:
                value = str(env[key]).lower()

                meta_key = [str(v).lower() for v in meta[key]]

                if set(meta_key) & set(["yes", "on", "true", "1"]):
                    if value not in ["no", "off", "false", "0"]:
                        found = True
                elif set(meta_key) & set(["no", "off", "false", "0"]):
                    if value in ["no", "off", "false", "0"]:
                        found = True
                elif value in meta_key:
                    found = True
            
            # If found any match from the list (OR), return
            if found:
                return True

        return False

    def update_env_with_values(env, fail_on_not_found=False):
        """
        Update any env key used as part of values in meta
        """
        import re
        for key in env:
            if key.startswith("+") and type(env[key]) != list:
                return {'return': 1, 'error': 'List value expected for {} in env'.format(key)}

            value = env[key]

            # Check cases such as --env.CM_SKIP_COMPILE
            if type(value)==bool:
                env[key] = str(value)
                continue

            tmp_values = re.findall(r'<<<(.*?)>>>', str(value))

            if not tmp_values:
                if key == 'CM_GIT_URL' and env.get('CM_GIT_AUTH', "no") == "yes":
                    if 'CM_GH_TOKEN' in env and '@' not in env['CM_GIT_URL']:
                        params = {}
                        params["token"] = env['CM_GH_TOKEN']
                        value = get_git_url("token", value, params)
                    elif 'CM_GIT_SSH' in env:
                        value = get_git_url("ssh", value)
                    env[key] = value

                continue

            for tmp_value in tmp_values:
                if tmp_value not in env and fail_on_not_found:
                    return {'return':1, 'error':'variable {} is not in env'.format(tmp_value)}
                if tmp_value in env:
                    value = value.replace("<<<"+tmp_value+">>>", str(env[tmp_value]))

            env[key] = value

        return {'return': 0}

    def check_version_constraints(i):
        """
        Internal: check version constaints and skip script artifact if constraints are not met
        """
        detected_version = i['detected_version']

        version = i.get('version', '')
        version_min = i.get('version_min', '')
        version_max = i.get('version_max', '')

        cmind = i['cmind']

        skip = False

        if version != '' and version != detected_version:
            skip = True

        if not skip and detected_version != '' and version_min != '':
            ry = cmind.access({'action':'compare_versions',
                               'automation':'utils,dc2743f8450541e3',
                               'version1':detected_version,
                               'version2':version_min})
            if ry['return']>0: return ry

            if ry['comparison'] < 0:
                skip = True

        if not skip and detected_version != '' and version_max != '':
            ry = cmind.access({'action':'compare_versions',
                               'automation':'utils,dc2743f8450541e3',
                               'version1':detected_version,
                               'version2':version_max})
            if ry['return']>0: return ry

            if ry['comparison'] > 0:
                skip = True

        return {'return':0, 'skip':skip}

    def prepare_and_run_script_with_postprocessing(i, postprocess="postprocess"):
        """
        Internal: prepare and run script with postprocessing that can be reused for version check
        """
        path = i['path']
        bat_ext = i['bat_ext']
        os_info = i['os_info']
        customize_code = i.get('customize_code', None)
        customize_common_input = i.get('customize_common_input',{})

        env = i.get('env', {})
        const = i.get('const', {})
        state = i.get('state', {})
        const_state = i.get('const_state', {})
        run_state = i.get('run_state', {})
        verbose = i.get('verbose', False)
        if not verbose: verbose = i.get('v', False)

        show_time = i.get('time', False)

        recursion = i.get('recursion', False)
        found_script_tags = i.get('found_script_tags', [])
        debug_script_tags = i.get('debug_script_tags', '')

        meta = i.get('meta',{})

        reuse_cached = i.get('reused_cached', False)
        recursion_spaces = i.get('recursion_spaces', '')

        tmp_file_run_state = i.get('tmp_file_run_state', '')
        tmp_file_run_env = i.get('tmp_file_run_env', '')
        tmp_file_state = i.get('tmp_file_state', '')
        tmp_file_run = i['tmp_file_run']
        local_env_keys = i.get('local_env_keys', [])
        local_env_keys_from_meta = i.get('local_env_keys_from_meta', [])
        posthook_deps = i.get('posthook_deps', [])
        add_deps_recursive = i.get('add_deps_recursive', {})
        recursion_spaces = i['recursion_spaces']
        remembered_selections = i.get('remembered_selections', {})
        variation_tags_string = i.get('variation_tags_string', '')
        found_cached = i.get('found_cached', False)
        script_automation = i['self']

        repro_prefix = i.get('repro_prefix', '')

        # Prepare script name
        check_if_run_script_exists = False
        script_name = i.get('script_name','').strip()
        if script_name == '':
            script_name = meta.get('script_name','').strip()
            if script_name !='':
                # Script name was added by user - we need to check that it really exists (on Linux or Windows)
                check_if_run_script_exists = True
        if script_name == '':
            # Here is the default script name - if it doesn't exist, we skip it. 
            # However, if it's explicitly specified, we check it and report
            # if it's missing ...
            script_name = 'run'

        if bat_ext == '.sh':
            run_script = get_script_name(env, path, script_name)
        else:
            run_script = script_name + bat_ext

        path_to_run_script = os.path.join(path, run_script)

        if check_if_run_script_exists and not os.path.isfile(path_to_run_script):
            return {'return':16, 'error':'script {} not found - please add one'.format(path_to_run_script)}

        # Update env and state with const
        utils.merge_dicts({'dict1':env, 'dict2':const, 'append_lists':True, 'append_unique':True})
        utils.merge_dicts({'dict1':state, 'dict2':const_state, 'append_lists':True, 'append_unique':True})

        # Update env with the current path
        if os_info['platform'] == 'windows' and ' ' in path:
            path = '"' + path + '"'

        cur_dir = os.getcwd()

        env['CM_TMP_CURRENT_SCRIPT_PATH'] = path
        env['CM_TMP_CURRENT_SCRIPT_WORK_PATH'] = cur_dir

        # Record state
        if tmp_file_state != '':
            r = utils.save_json(file_name = tmp_file_state, meta = state)
            if r['return']>0: return r

        rr = {'return':0}

        # If batch file exists, run it with current env and state
        if os.path.isfile(path_to_run_script) and not reuse_cached:
            if tmp_file_run_state != '' and os.path.isfile(tmp_file_run_state):
                os.remove(tmp_file_run_state)
            if tmp_file_run_env != '' and os.path.isfile(tmp_file_run_env):
                os.remove(tmp_file_run_env)

            run_script = tmp_file_run + bat_ext
            run_script_without_cm = tmp_file_run + '-without-cm' + bat_ext

            if verbose:
                logging.info('')
                logging.info(recursion_spaces + '  - Running native script "{}" from temporal script "{}" in "{}" ...'.format(path_to_run_script, run_script, cur_dir))
                logging.info('')

            if not run_state.get('tmp_silent', False):
                logging.info(recursion_spaces + '       ! cd {}'.format(cur_dir))
                logging.info(recursion_spaces + '       ! call {} from {}'.format(path_to_run_script, run_script))

            # Prepare env variables
            import copy
            script = copy.deepcopy(os_info['start_script'])

            # Check if script_prefix in the state from other components
            script_prefix = state.get('script_prefix',[])
            if len(script_prefix)>0:
                script += script_prefix + ['\n']

            script += convert_env_to_script(env, os_info)

            # Append batch file to the tmp script
            script.append('\n')
            script.append(os_info['run_bat'].replace('${bat_file}', '"'+path_to_run_script+'"') + '\n')

            # Prepare and run script
            r = record_script(run_script, script, os_info)
            if r['return']>0: return r

            # Save file to run without CM
            if debug_script_tags !='' and all(item in found_script_tags for item in debug_script_tags.split(',')):
                import shutil
                shutil.copy(run_script, run_script_without_cm)

                logging.info('================================================================================')
                logging.info('Debug script to run without CM was recorded: {}'.format(run_script_without_cm))
                logging.info('================================================================================')

            # Run final command
            cmd = os_info['run_local_bat_from_python'].replace('${bat_file}', run_script)

            rc = os.system(cmd)

            if rc>0 and not i.get('ignore_script_error', False):
                # Check if print files when error
                print_files = meta.get('print_files_if_script_error', [])
                if len(print_files)>0:
                   for pr in print_files:
                       if os.path.isfile(pr):
                           r = utils.load_txt(file_name = pr)
                           if r['return'] == 0:
                               logging.info("========================================================")
                               logging.info("Print file {}:".format(pr))
                               logging.info("")
                               logging.info(r['string'])
                               logging.info("")

                # Check where to report errors and failures
                repo_to_report = run_state.get('script_entry_repo_to_report_errors', '')

                if repo_to_report == '':
                    script_repo_alias = run_state.get('script_repo_alias', '')
                    script_repo_git = run_state.get('script_repo_git', False)

                    if script_repo_git and script_repo_alias!='':
                        repo_to_report = 'https://github.com/'+script_repo_alias.replace('@','/')+'/issues'
                
                if repo_to_report == '':
                    repo_to_report = 'https://github.com/mlcommons/ck/issues'

                note = '''
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Note that it is often a portability issue of a third-party tool or a native script 
wrapped and unified by this CM script (automation recipe). Please re-run
this script with --repro flag and report this issue with the original
command line, cm-repro directory and full log here:

{}

The CM concept is to collaboratively fix such issues inside portable CM scripts 
to make existing tools and native scripts more portable, interoperable 
and deterministic. Thank you'''.format(repo_to_report)

                rr = {'return':2, 'error':'Portable CM script failed (name = {}, return code = {})\n\n{}'.format(meta['alias'], rc, note)}

                if repro_prefix != '':
                    dump_repro(repro_prefix, rr, run_state)
                
                return rr

            # Load updated state if exists
            if tmp_file_run_state != '' and os.path.isfile(tmp_file_run_state):
                r = utils.load_json(file_name = tmp_file_run_state)
                if r['return']>0: return r

                updated_state = r['meta']

                utils.merge_dicts({'dict1':state, 'dict2':updated_state, 'append_lists':True, 'append_unique':True})

            # Load updated env if exists
            if tmp_file_run_env != '' and os.path.isfile(tmp_file_run_env):
                r = utils.load_txt(file_name = tmp_file_run_env)
                if r['return']>0: return r

                r = utils.convert_env_to_dict(r['string'])
                if r['return']>0: return r

                updated_env = r['dict']

                utils.merge_dicts({'dict1':env, 'dict2':updated_env, 'append_lists':True, 'append_unique':True})

        if postprocess != '' and customize_code is not None and postprocess in dir(customize_code):
            if not run_state.get('tmp_silent', False):
                logging.info(recursion_spaces+'       ! call "{}" from {}'.format(postprocess, customize_code.__file__))
        
        if len(posthook_deps)>0 and (postprocess == "postprocess"):
            r = script_automation._call_run_deps(posthook_deps, local_env_keys, local_env_keys_from_meta, env, state, const, const_state,
                add_deps_recursive, recursion_spaces, remembered_selections, variation_tags_string, found_cached, debug_script_tags, verbose, show_time, ' ', run_state)
            if r['return']>0: return r

        if (postprocess == "postprocess") and customize_code is not None and 'postprocess' in dir(customize_code):
            rr = run_postprocess(customize_code, customize_common_input, recursion_spaces, env, state, const,
                    const_state, meta, verbose, i) # i as run_script_input
        elif (postprocess == "detect_version") and customize_code is not None and 'detect_version' in dir(customize_code):
            rr = run_detect_version(customize_code, customize_common_input, recursion_spaces, env, state, const,
                    const_state, meta, verbose)

        return rr

    def run_detect_version(customize_code, customize_common_input, recursion_spaces, env, state, const, const_state, meta, verbose=False):
        if customize_code is not None and 'detect_version' in dir(customize_code):
            import copy

            if verbose:
                logging.info(recursion_spaces+'  - Running detect_version ...')

            # Update env and state with const
            utils.merge_dicts({'dict1':env, 'dict2':const, 'append_lists':True, 'append_unique':True})
            utils.merge_dicts({'dict1':state, 'dict2':const_state, 'append_lists':True, 'append_unique':True})

            ii = copy.deepcopy(customize_common_input)
            ii['env'] = env
            ii['state'] = state
            ii['meta'] = meta

            r = customize_code.detect_version(ii)
            return r

        return {'return': 0}

    def run_postprocess(customize_code, customize_common_input, recursion_spaces, env, state, const, const_state, meta, verbose=False, run_script_input=None):
        if customize_code is not None and 'postprocess' in dir(customize_code):
            import copy

            if verbose:
                logging.info(recursion_spaces+'  - Running postprocess ...')

            # Update env and state with const
            utils.merge_dicts({'dict1':env, 'dict2':const, 'append_lists':True, 'append_unique':True})
            utils.merge_dicts({'dict1':state, 'dict2':const_state, 'append_lists':True, 'append_unique':True})

            ii = copy.deepcopy(customize_common_input)
            ii['env'] = env
            ii['state'] = state
            ii['meta'] = meta

            if run_script_input != None:
                ii['run_script_input'] = run_script_input 

            r = customize_code.postprocess(ii)
            return r

        return {'return': 0}

    def get_script_name(env, path, script_name = 'run'):
        """
        Internal: find the most appropriate run script name for the detected OS
        """
        from os.path import exists

        tmp_suff1 = env.get('CM_HOST_OS_FLAVOR', '')
        tmp_suff2 = env.get('CM_HOST_OS_VERSION', '')
        tmp_suff3 = env.get('CM_HOST_PLATFORM_FLAVOR', '')

        if exists(os.path.join(path, script_name+'-' + tmp_suff1 + '-'+ tmp_suff2 + '-' + tmp_suff3 + '.sh')):
            return script_name+'-' + tmp_suff1 + '-' + tmp_suff2 + '-' + tmp_suff3 + '.sh'
        elif exists(os.path.join(path, script_name+'-' + tmp_suff1 + '-' + tmp_suff3 + '.sh')):
            return script_name+'-' + tmp_suff1 + '-' + tmp_suff3 + '.sh'
        elif exists(os.path.join(path, script_name+'-' + tmp_suff1 + '-' + tmp_suff2 + '.sh')):
            return script_name+'-' + tmp_suff1 + '-' + tmp_suff2 + '.sh'
        elif exists(os.path.join(path, script_name+'-' + tmp_suff1 + '.sh')):
            return script_name+'-' + tmp_suff1 + '.sh'
        elif exists(os.path.join(path, script_name+'-' + tmp_suff3 + '.sh')):
            return script_name+'-' + tmp_suff3 + '.sh'
        else:
            return script_name+'.sh';

    def update_env_keys(env, env_key_mappings):
        """
        Internal: convert env keys as per the given mapping
        """
        for key_prefix in env_key_mappings:
            for key in list(env):
                if key.startswith(key_prefix):
                    new_key = key.replace(key_prefix, env_key_mappings[key_prefix])
                    env[new_key] = env[key]
                    #del(env[key])

    def convert_env_to_script(env, os_info, start_script = []):
        """
        Internal: convert env to script for a given platform
        """
        import copy
        script = copy.deepcopy(start_script)

        windows = True if os_info['platform'] == 'windows' else False

        for k in sorted(env):
            env_value = env[k]

            if windows:
                x = env_value
                if type(env_value)!=list:
                    x = [x]

                xx = []
                for v in x:
                    # If " is already in env value, it means that there was some custom processing to consider special characters

                    y=str(v)

                    if '"' not in y:
                        for z in ['|', '&', '>', '<']:
                            if z in y:
                                y = '"'+y+'"'
                                break
                    xx.append(y)

                env_value = xx if type(env_value)==list else xx[0]

            # Process special env 
            key = k

            if k.startswith('+'):
                # List and append the same key at the end (+PATH, +LD_LIBRARY_PATH, +PYTHONPATH)
                key=k[1:]
                first = key[0]
                env_separator = os_info['env_separator']
                # If key starts with a symbol use it as the list separator (+ CFLAG will use ' ' the 
                # list separator while +;TEMP will use ';' as the separator)
                if not first.isalnum():
                    env_separator = first
                    key=key[1:]

                env_value = env_separator.join(env_value) + \
                    env_separator + \
                    os_info['env_var'].replace('env_var', key)

            v = os_info['set_env'].replace('${key}', key).replace('${value}', str(env_value))

            script.append(v)

        return script

    def record_script(run_script, script, os_info):
        """
        Internal: record script and chmod 755 on Linux
        """
        final_script = '\n'.join(script)

        if not final_script.endswith('\n'):
            final_script += '\n'

        r = utils.save_txt(file_name=run_script, string=final_script)
        if r['return']>0: return r

        if os_info.get('set_exec_file','')!='':
            cmd = os_info['set_exec_file'].replace('${file_name}', run_script)
            rc = os.system(cmd)

        return {'return':0}

    def clean_tmp_files(clean_files, recursion_spaces):
        """
        Internal: clean tmp files
        """
        for tmp_file in clean_files:
            if os.path.isfile(tmp_file):
                os.remove(tmp_file)

        return {'return':0}

    def update_dep_info(dep, new_info):
        """
        Internal: add additional info to a dependency
        """
        for info in new_info:
            if info == "tags":
                tags = dep.get('tags', '')
                tags_list = tags.split(",")
                new_tags_list = new_info["tags"].split(",")
                combined_tags = tags_list + list(set(new_tags_list) - set(tags_list))
                dep['tags'] = ",".join(combined_tags)
            else:
                dep[info] = new_info[info]

    def update_deps(deps, add_deps, fail_error=False):
        """
        Internal: add deps tags, version etc. by name
        """
        new_deps_info = {}
        for new_deps_name in add_deps:
            dep_found = False
            for dep in deps:
                names = dep.get('names',[])
                if new_deps_name in names:
                    update_dep_info(dep, add_deps[new_deps_name])
                    dep_found = True
            if not dep_found and fail_error:
                return {'return':1, 'error':new_deps_name + ' is not one of the dependency'}

        return {'return':0}

    def append_deps(deps, new_deps):
        """
        Internal: add deps from meta
        """
        for new_dep in new_deps:
            existing = False
            new_dep_names = new_dep.get('names',[])
            if len(new_dep_names)>0:
                for i in range(len(deps)):
                    dep = deps[i]
                    dep_names = dep.get('names',[])
                    if len(dep_names)>0:
                        if set(new_dep_names) == set(dep_names):
                            deps[i] = new_dep
                            existing = True
                            break
            else: #when no name, check for tags
                new_dep_tags = new_dep.get('tags')
                new_dep_tags_list = new_dep_tags.split(",")
                for i in range(len(deps)):
                    dep = deps[i]
                    dep_tags_list = dep.get('tags').split(",")
                    if set(new_dep_tags_list) == set (dep_tags_list):
                        deps[i] = new_dep
                        existing = True
                        break

            if not existing:
                deps.append(new_dep)

        return {'return':0}

    def update_deps_from_input(deps, post_deps, prehook_deps, posthook_deps, i):
        """
        Internal: update deps from meta
        """
        add_deps_info_from_input = i.get('ad',{})
        if not add_deps_info_from_input:
            add_deps_info_from_input = i.get('add_deps',{})
        else:
            utils.merge_dicts({'dict1':add_deps_info_from_input, 'dict2':i.get('add_deps', {}), 'append_lists':True, 'append_unique':True})

        add_deps_recursive_info_from_input = i.get('adr', {})
        if not add_deps_recursive_info_from_input:
            add_deps_recursive_info_from_input = i.get('add_deps_recursive', {})
        else:
            utils.merge_dicts({'dict1':add_deps_recursive_info_from_input, 'dict2':i.get('add_deps_recursive', {}), 'append_lists':True, 'append_unique':True})

        if add_deps_info_from_input:
            r1 = update_deps(deps, add_deps_info_from_input, True)
            r2 = update_deps(post_deps, add_deps_info_from_input, True)
            r3 = update_deps(prehook_deps, add_deps_info_from_input, True)
            r4 = update_deps(posthook_deps, add_deps_info_from_input, True)
            if r1['return']>0 and r2['return']>0 and r3['return']>0 and r4['return']>0: return r1
        if add_deps_recursive_info_from_input:
            update_deps(deps, add_deps_recursive_info_from_input)
            update_deps(post_deps, add_deps_recursive_info_from_input)
            update_deps(prehook_deps, add_deps_recursive_info_from_input)
            update_deps(posthook_deps, add_deps_recursive_info_from_input)

        return {'return':0}

    def update_env_from_input_mapping(env, inp, input_mapping):
        """
        Internal: update env from input and input_mapping
        """
        for key in input_mapping:
            if key in inp:
                env[input_mapping[key]] = inp[key]

    def update_state_from_meta(meta, env, state, deps, post_deps, prehook_deps, posthook_deps, new_env_keys, new_state_keys, i):
        """
        Internal: update env and state from meta
        """
        default_env = meta.get('default_env',{})
        for key in default_env:
            env.setdefault(key, default_env[key])
        update_env = meta.get('env', {})
        env.update(update_env)

        update_state = meta.get('state', {})
        utils.merge_dicts({'dict1':state, 'dict2':update_state, 'append_lists':True, 'append_unique':True})

        new_deps = meta.get('deps', [])
        if len(new_deps)>0:
            append_deps(deps, new_deps)

        new_post_deps = meta.get("post_deps", [])
        if len(new_post_deps) > 0:
            append_deps(post_deps, new_post_deps)

        new_prehook_deps = meta.get("prehook_deps", [])
        if len(new_prehook_deps) > 0:
            append_deps(prehook_deps, new_prehook_deps)

        new_posthook_deps = meta.get("posthook_deps", [])
        if len(new_posthook_deps) > 0:
            append_deps(posthook_deps, new_posthook_deps)

        add_deps_info = meta.get('ad', {})
        if not add_deps_info:
            add_deps_info = meta.get('add_deps',{})
        else:
            utils.merge_dicts({'dict1':add_deps_info, 'dict2':meta.get('add_deps', {}), 'append_lists':True, 'append_unique':True})
        if add_deps_info:
            r1 = update_deps(deps, add_deps_info, True)
            r2 = update_deps(post_deps, add_deps_info, True)
            r3 = update_deps(prehook_deps, add_deps_info, True)
            r4 = update_deps(posthook_deps, add_deps_info, True)
            if r1['return']>0 and r2['return']>0 and r3['return'] > 0 and r4['return'] > 0: return r1

        input_mapping = meta.get('input_mapping', {})
        if input_mapping:
            update_env_from_input_mapping(env, i['input'], input_mapping)

        # Possibly restrict this to within docker environment
        new_docker_settings = meta.get('docker')
        if new_docker_settings:
            docker_settings = state.get('docker', {})
            utils.merge_dicts({'dict1':docker_settings, 'dict2':new_docker_settings, 'append_lists':True, 'append_unique':True})
            state['docker'] = docker_settings

        new_env_keys_from_meta = meta.get('new_env_keys', [])
        if new_env_keys_from_meta:
            new_env_keys += new_env_keys_from_meta

        new_state_keys_from_meta = meta.get('new_state_keys', [])
        if new_state_keys_from_meta:
            new_state_keys += new_state_keys_from_meta

        return {'return':0}

    def update_adr_from_meta(deps, post_deps, prehook_deps, posthook_deps, add_deps_recursive_info):
        """
        Internal: update add_deps_recursive from meta
        """
        if add_deps_recursive_info:
            update_deps(deps, add_deps_recursive_info)
            update_deps(post_deps, add_deps_recursive_info)
            update_deps(prehook_deps, add_deps_recursive_info)
            update_deps(posthook_deps, add_deps_recursive_info)

        return {'return':0}

    def get_adr(meta):
        add_deps_recursive_info = meta.get('adr', {})
        if not add_deps_recursive_info:
            add_deps_recursive_info = meta.get('add_deps_recursive',{})
        else:
            utils.merge_dicts({'dict1':add_deps_recursive_info, 'dict2':meta.get('add_deps_recursive', {}), 'append_lists':True, 'append_unique':True})
        return add_deps_recursive_info

    def detect_state_diff(env, saved_env, new_env_keys, new_state_keys, state, saved_state):
        """
        Internal: detect diff in env and state
        """
        new_env = {}
        new_state = {}

        # Check if leave only specific keys or detect diff automatically
        for k in new_env_keys:
            if '?' in k or '*' in k:
                import fnmatch
                for kk in env:
                    if fnmatch.fnmatch(kk, k):
                        new_env[kk] = env[kk]
            elif k in env:
                new_env[k] = env[k]
            elif "<<<" in k:
                import re
                tmp_values = re.findall(r'<<<(.*?)>>>', k)
                for tmp_value in tmp_values:
                    if tmp_value in env:
                        value = env[tmp_value]
                        if value in env:
                            new_env[value] = env[value]

        for k in new_state_keys:
            if '?' in k or '*' in k:
                import fnmatch
                for kk in state:
                    if fnmatch.fnmatch(kk, k):
                        new_state[kk] = state[kk]
            elif k in state:
                new_state[k] = state[k]
            elif "<<<" in k:
                import re
                tmp_values = re.findall(r'<<<(.*?)>>>', k)
                for tmp_value in tmp_values:
                    if tmp_value in state:
                        value = state[tmp_value]
                        if value in state:
                            new_state[value] = state[value]

        return {'return':0, 'env':env, 'new_env':new_env, 'state':state, 'new_state':new_state}

    def select_script_artifact(lst, text, recursion_spaces, can_skip, script_tags_string, quiet, verbose):
        """
        Internal: select script
        """
        string1 = recursion_spaces+'    - More than 1 {} found for "{}":'.format(text,script_tags_string)

        # If quiet, select 0 (can be sorted for determinism)
        if quiet:
            if verbose:
                logging.info(string1)
                logging.info('')
                logging.info('Selected default due to "quiet" mode')

            return 0

        # Select 1 and proceed
        logging.info(string1)

        logging.info('')
        num = 0

        for a in lst:
            meta = a.meta

            name = meta.get('name', '')

            s = a.path
            if name !='': s = '"'+name+'" '+s

            x = recursion_spaces+'      {}) {} ({})'.format(num, s, ','.join(meta['tags']))

            version = meta.get('version','')
            if version!='':
                x+=' (Version {})'.format(version)

            logging.info(x)
            num+=1

        logging.info('')

        s = 'Make your selection or press Enter for 0'
        if can_skip:
            s += ' or use -1 to skip'

        x = input(recursion_spaces+'      '+s+': ')
        x = x.strip()
        if x == '': x = '0'

        selection = int(x)

        if selection <0 and not can_skip:
            selection = 0

        if selection <0:
            logging.info('')
            logging.info(recursion_spaces+'      Skipped')
        else:
            if selection >= num:
                selection = 0

            logging.info('')
            logging.info(recursion_spaces+'      Selected {}: {}'.format(selection, lst[selection].path))

        return selection

    def check_versions(cmind, cached_script_version, version_min, version_max):
        """
        Internal: check versions of the cached script
        """
        skip_cached_script = False

        if cached_script_version != '':
            if version_min != '':
                ry = cmind.access({'action':'compare_versions',
                                        'automation':'utils,dc2743f8450541e3',
                                        'version1':cached_script_version,
                                        'version2':version_min})
                if ry['return']>0: return ry

                if ry['comparison'] < 0:
                    skip_cached_script = True

            if not skip_cached_script and version_max != '':
                ry = cmind.access({'action':'compare_versions',
                                   'automation':'utils,dc2743f8450541e3',
                                   'version1':cached_script_version,
                                   'version2':version_max})
                if ry['return']>0: return ry

                if ry['comparison'] > 0:
                    skip_cached_script = True

        return skip_cached_script

    def get_git_url(get_type, url, params = {}):
        from giturlparse import parse
        p = parse(url)
        if get_type == "ssh":
            return p.url2ssh
        elif get_type == "token":
            token = params['token']
            return "https://git:" + token + "@" + p.host + "/" + p.owner + "/" + p.repo
        return url

    def can_write_to_current_directory():
        import tempfile

        cur_dir = os.getcwd()

        tmp_file_name = next(tempfile._get_candidate_names())+'.tmp'

        tmp_path = os.path.join(cur_dir, tmp_file_name)

        try:
            tmp_file = open(tmp_file_name, 'w')
        except Exception as e:
            return False

        tmp_file.close()

        os.remove(tmp_file_name)

        return True

    def dump_repro_start(repro_prefix, ii):
        import json

        # Clean reproducibility and experiment files
        for f in ['cm-output.json', 'version_info.json', '-input.json', '-info.json', '-output.json', '-run-state.json']:
            ff = repro_prefix+f if f.startswith('-') else f
            if os.path.isfile(ff):
                try:
                    os.remove(ff)
                except:
                    pass

        try:
            with open(repro_prefix+'-input.json', 'w', encoding='utf-8') as f:
                json.dump(ii, f, ensure_ascii=False, indent=2)
        except:
            pass

        # Get some info
        info = {}

        try:
            import platform
            import sys

            info['host_os_name'] = os.name
            info['host_system'] = platform.system()
            info['host_os_release'] = platform.release()
            info['host_machine'] = platform.machine()
            info['host_architecture'] = platform.architecture()
            info['host_python_version'] = platform.python_version()
            info['host_sys_version'] = sys.version

            r = utils.gen_uid()
            if r['return']==0:
                info['run_uid'] = r['uid']

            r = utils.get_current_date_time({})
            if r['return']==0: 
                info['run_iso_datetime'] = r['iso_datetime']

            with open(repro_prefix+'-info.json', 'w', encoding='utf-8') as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
        except:
            pass


        # For experiment
        cm_output = {}

        cm_output['tmp_test_value']=10.0

        cm_output['info']=info
        cm_output['input']=ii

        try:
            with open('cm-output.json', 'w', encoding='utf-8') as f:
                json.dump(cm_output, f, ensure_ascii=False, indent=2)
        except:
            pass

        return {'return': 0}

    def dump_repro(repro_prefix, rr, run_state):
        import json
        import copy

        try:
            with open(repro_prefix+'-output.json', 'w', encoding='utf-8') as f:
                json.dump(rr, f, ensure_ascii=False, indent=2)
        except:
            pass

        try:
            with open(repro_prefix+'-run-state.json', 'w', encoding='utf-8') as f:
                json.dump(run_state, f, ensure_ascii=False, indent=2)
        except:
            pass

        # For experiment
        cm_output = {}

        # Attempt to read
        try:
            r =  utils.load_json('cm-output.json')
            if r['return']==0:
                cm_output = r['meta']
        except:
            pass

        cm_output['output'] = rr
        cm_output['state'] = copy.deepcopy(run_state)

        # Try to load version_info.json
        version_info = {}

        version_info_orig = {}

        if 'version_info' in cm_output['state']:
            version_info_orig = cm_output['state']['version_info']
            del(cm_output['state']['version_info'])

        try:
            r =  utils.load_json('version_info.json')
            if r['return']==0:
                version_info_orig += r['meta']

                for v in version_info_orig:
                    for key in v:
                        dep = v[key]
                        version_info[key] = dep

        except:
            pass

        if len(version_info)>0:
            cm_output['version_info'] = version_info

        if rr['return'] == 0:
            # See https://cTuning.org/ae
            cm_output['acm_ctuning_repro_badge_available'] = True
            cm_output['acm_ctuning_repro_badge_functional'] = True

        try:
            with open('cm-output.json', 'w', encoding='utf-8') as f:
                json.dump(cm_output, f, ensure_ascii=False, indent=2, sort_keys=True)
        except:
            pass


        return {'return': 0}

    # Demo to show how to use CM components independently if needed
    if __name__ == "__main__":
        import cmind
        auto = CAutomation(cmind, __file__)

        r=auto.test({'x':'y'})

        logging.info(r)