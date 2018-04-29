import os
import pprint

import matplotlib.pyplot as plt
import numpy as np
import scipy.interpolate as interp
import scipy.optimize as opt
import scipy.signal as sig

from bag.util.search import BinaryIterator
from bag.util.search import minimize_cost_golden_float
from bag.data.lti import LTICircuit
from bag.data.lti import get_w_3db
from bag.data.lti import get_stability_margins
from verification_ec.mos.query import MOSDBDiscrete

from bag import BagProject
from bag.io import load_sim_results, save_sim_results, load_sim_file

# Additional constraints
# Channel length of 90 nm:
# pmos_spec = 'specs_mos_char/pch_w0d5.yaml' ***
# nmos_spec = 'specs_mos_char/nch_w0d5_90n.yaml'
# LVT threshold flavor:
# intent = 'lvt'

# Global variables
# Schematic generator library/cell name
tb_lib = 'project'
tb_cell = 'ph2_sa'
# Library to create new schematics in
impl_lib = 'AAAFOO_ph2_sa'
# Directory to save simulation data
data_dir = os.path.join('data', 'ph2_sa')

# Create data directory if it doesn't exist
os.makedirs(data_dir, exist_ok = True)


def design_strong_arm(specs):
    vdd = specs['vdd']
    vin_cm = specs['vin_cm']
    vamp = specs['vamp']
    vmin = specs['vmin']
    cff = specs['cff']
    tper = specs['tper']
    tr = specs['tr']
    tsu = specs['tsu']
    cyield = specs['cyield']
    ratio_min = specs['ratio_min']
    ratio_max = specs['ratio_max']
    n_ratio = specs['n_ratio']
    scale_min = specs['scale_min']
    scale_max = specs['scale_max']
    n_scale = specs['n_scale']

    # New generated testbench name
    tb_name = 'ph2_sa'
    fname = os.path.join(data_dir, '%s.data' % tb_name)
    print('Creating testbench %s...' % tb_name)

    # Create schematic generator
    tb_sch = prj.create_design_module(tb_lib, tb_cell)
    tb_sch.design()
    tb_sch.implement_design(impl_lib, top_cell_name = tb_name)

    n = 0
    scale_list = np.linspace(scale_min, scale_max, n_scale)
    for scale in scale_list:
        ratio_list = np.linspace(ratio_min, ratio_max, n_ratio)
        for ratio in ratio_list:
            # Copy and load ADEXL state of generated testbench
            tb_sch.implement_design(impl_lib, top_cell_name = tb_name)
            tb_obj = prj.configure_testbench(impl_lib, tb_name)
            tb_obj.set_parameter('vdd', vdd)
            tb_obj.set_parameter('vin_cm', vin_cm)
            tb_obj.set_parameter('vamp', vamp/2)
            tb_obj.set_parameter('cff', cff)
            tb_obj.set_parameter('tper', tper)
            tb_obj.set_parameter('tr', tr)
            tb_obj.set_parameter('tsu', tsu)

            nfpc = 2
            nfd = scale * ratio
            nft = nfd
            nfn = scale
            ratio_pn = 1
            nfp = ratio_pn

            tb_obj.set_parameter('nfpc', nfpc)
            tb_obj.set_parameter('nfd', scale * ratio)
            tb_obj.set_parameter('nft', scale * ratio)
            tb_obj.set_parameter('nfn', nfn)
            tb_obj.set_parameter('ratio_pn', ratio_pn)
            tb_obj.set_parameter('nfp', nfp)

            # Update testbench changes and run simulation
            tb_obj.update_testbench()
            n = n + 1
            print('Simulating testbench %d...' % n)
            save_dir = tb_obj.run_simulation()

            # Load simulation results into Python
            print('Simulation done, saving results...')
            results = load_sim_results(save_dir)
            # Save Simulation results to data directory
            save_sim_results(results, fname)

            vin_ff = results['vin_ff']
            vin_ff2 = results['vin_ff2']

            if vin_ff >= vmin and vin_ff2 <= -vmin:
                design = dict(
                	nfpc = nfpc,
                    nfd = nfd,
                    nft = nft,
                    nfn = nfn,
                    nfp = nfp,
                    Vodp = vin_ff,
                    Vodm = vin_ff2
                    )
                pprint.pprint(design)
    return


def run_main():
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('Creating BAG project')
        bprj = BagProject()
    else:
        print('Loading BAG project')
        bprj = local_dict['bprj']

    specs = dict(
        vdd = 1.2,
        vin_cm = 0.6,
        vamp = 20e-3, # 20, 20, 5
        vmin = 800e-3,
        cff = 5e-15, # 5, 5, 2.5
        tper = 200e-12, # 200, 200, 300
        tr = 20e-12,
        tsu = 30e-12,
        cyield = 0, # 0 (unconstrained), 0.9999, 0.9999
        ratio_min = 1,
        ratio_max = 5,
        n_ratio = 5,
        scale_min = 1,
        scale_max = 5,
        n_scale = 5
        )

    design_strong_arm(specs)


if __name__ == '__main__':
    run_main()