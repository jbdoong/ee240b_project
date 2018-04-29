# -*- coding: utf-8 -*-

import os
import pkg_resources
from typing import Dict

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'ph2_sa_tb.yaml'))


# noinspection PyPep8Naming
class project__ph2_sa_tb(Module):
    """Module for library project cell ph2_sa_tb.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
        )

    def design(self):
        """To be overridden by subclasses to design this module.

        This method should fill in values for all parameters in
        self.parameters.  To design instances of this module, you can
        call their design() method or any other ways you coded.

        To modify schematic structure, call:

        rename_pin()
        delete_instance()
        replace_instance_master()
        reconnect_instance_terminal()
        restore_instance()
        array_instance()
        """

        self.instances['M7'].design(w=0.5e-6, l=90e-9, nf='nft', intent='lvt')
        self.instances['M1'].design(w=0.5e-6, l=90e-9, nf='nfd', intent='lvt')
        self.instances['M2'].design(w=0.5e-6, l=90e-9, nf='nfd', intent='lvt')
        self.instances['M3'].design(w=0.5e-6, l=90e-9, nf='nfn', intent='lvt')
        self.instances['M4'].design(w=0.5e-6, l=90e-9, nf='nfn', intent='lvt')
        self.instances['M5'].design(w=0.5e-6, l=90e-9, nf='nfp', intent='lvt')
        self.instances['M6'].design(w=0.5e-6, l=90e-9, nf='nfp', intent='lvt')
        self.instances['S1'].design(w=0.5e-6, l=90e-9, nf='nfpc', intent='lvt')
        self.instances['S2'].design(w=0.5e-6, l=90e-9, nf='nfpc', intent='lvt')
        self.instances['S3'].design(w=0.5e-6, l=90e-9, nf='nfpc', intent='lvt')
        self.instances['S4'].design(w=0.5e-6, l=90e-9, nf='nfpc', intent='lvt')
        
        pass
