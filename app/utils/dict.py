from copy import deepcopy

# RFC: https://datatracker.ietf.org/doc/html/rfc7386
def merge_patch(patch: dict, resource: dict) -> None:
    """
    JSON merge patch two dicts.

    Return nothing as the resource is directly modified

    You can look at tests/test_utils/test_json_merge_patch.py to understand the different situation and outcomes.

    :param patch: the pacth dict
    :type patch: dict
    :param resource: the resource (target) dict.
    :type resource: dict
    :raises ValueError: If trying to update a key with a dict whereas the resource doesn't have a dict.
    """

    for patch_key, patch_value in patch.items():
        if patch_value is None:
            #If patch value is none, the resource value is remove
            resource.pop(patch_key, None)
        elif patch_key in resource:
            #Resource already have the key of the patch
            resource_value = resource[patch_key]
            if resource_value is None:
                #Resource value is None, simply add the patch value
                resource[patch_key] = patch_value
            elif isinstance(resource_value, dict):
                #Resource value is a dict
                if isinstance(patch_value, dict):
                    #Patch value is also a dict, merge them.
                    merge_patch(patch_value, resource_value)
                else:
                    #Patch value is not a dict, unknwon behavior, raise a exception
                    raise ValueError(f"Patch object for {patch_key} has a dict value, when the resource is not")
            else:
                #resource value is not none nor a dict, update the value
                resource[patch_key] = patch_value
        else:
            #Value not present in resource
            if isinstance(patch_value, dict):
                #Clean the None in the dict with en empty resource
                new_value: dict = {}
                merge_patch(patch_value, new_value)
                if new_value:
                    #Only add the value if the dict is not empty
                    resource[patch_key] = new_value
            else:   
                #Not a dict, simply add it 
                resource[patch_key] = patch_value


def set_origin_from_settings(name:str, new_param: dict, default_param: dict) -> dict:
    """
    Param from new_param that are different from default_param will be
    marked as "domain"

    name is the new param's name could be "sogo.nu" or "rule: my_rule_name"
    default param should be complete.
    new_param may be partial.

    The return is a dict

    :param new_param: _description_
    :type new_param: dict
    :param default_param: _description_
    :type default_param: dict
    """
    origin_dict: dict = {}
    ref_new_param = deepcopy(new_param)
    for default_key, default_value in default_param.items():
        if isinstance(default_value, dict):
            if default_key in ref_new_param:
                origin_dict[default_key] = set_origin_from_settings(name, ref_new_param[default_key], default_value)
                ref_new_param.pop(default_key, None)
            else:
                origin_dict[default_key] = dict((sub_key, "default") for sub_key in default_value.keys())
        else:
            if default_key in ref_new_param:
                if ref_new_param[default_key] != default_param[default_key]:
                    origin_dict[default_key] = name
                else:
                    origin_dict[default_key] = "default"
                ref_new_param.pop(default_key, None)
            else:
                origin_dict[default_key] = "default"
    for new_key, new_value in ref_new_param.items():
        if isinstance(new_value, dict):
            origin_dict[new_key] = set_origin_from_settings(name, new_value, {})
        else:
            origin_dict[new_key] = name
    return origin_dict