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
# pmos_spec = 'specs_mos_char/pch_w0d5_90n.yaml' ***
# nmos_spec = 'specs_mos_char/nch_w0d5_90n.yaml'
# LVT threshold flavor:
# intent = 'lvt'

# Global variables
# Schematic generator library/cell name
tb_lib = 'project'
tb_cell = 'ph3_sa_tb'
# Library to create new schematics in
impl_lib = 'AAAFOO_ph3_sa_tb'
# Directory to save simulation data
data_dir = os.path.join('data', 'ph3_sa_tb')

# Create data directory if it doesn't exist
os.makedirs(data_dir, exist_ok = True)


def get_db(spec_file, intent, interp_method = 'spline', sim_env = 'tt'):
    # Initialize transistor database from simulation data
    mos_db = MOSDBDiscrete([spec_file], interp_method = interp_method)
    # Set process corners
    mos_db.env_list = [sim_env]
    # Set layout parameters
    mos_db.set_dsn_params(intent = intent)
    return mos_db


def design_strong_arm(specs):
    nch_db = specs['nch_db']
    vdd = specs['vdd']
    vin_cm = specs['vin_cm']
    vbig = specs['vbig']
    vamp = specs['vamp']
    vin_off = specs['vin_off']
    vmin = specs['vmin']
    cff = specs['cff']
    tper = specs['tper']
    tr = specs['tr']
    tsu = specs['tsu']
    cyield = specs['cyield']
    scale_min = specs['scale_min']
    scale_max = specs['scale_max']
    n_scale = specs['n_scale']
    ratio_min = specs['ratio_min']
    ratio_max = specs['ratio_max']
    n_ratio = specs['n_ratio']
    ratio_pn_min = specs['ratio_pn_min']
    ratio_pn_max = specs['ratio_pn_max']
    n_ratio_pn = specs['n_ratio_pn']

    # New generated testbench name
    tb_name = 'ph3_sa_tb'
    fname = os.path.join(data_dir, '%s.data' % tb_name)
    print('Creating testbench %s...' % tb_name)

    # Create schematic generator
    tb_sch = prj.create_design_module(tb_lib, tb_cell)
    tb_sch.design()
    tb_sch.implement_design(impl_lib, top_cell_name = tb_name)
    tb_obj = prj.configure_testbench(impl_lib, tb_name) # ***

    n = 0
    min_power = 1
    best_design = []

    # scale_iter = BinaryIterator(scale_min, scale_max, step = 2)
    # while scale_iter.has_next():
        # scale = scale_iter.get_next();
    scale_list = np.linspace(scale_min, scale_max, n_scale)
    for scale in scale_list:

        ratio_iter = BinaryIterator(ratio_min, ratio_max, step = 2)
        while ratio_iter.has_next():
            ratio = ratio_iter.get_next()
        # ratio_list = np.linspace(ratio_min, ratio_max, n_ratio)
        # for ratio in ratio_list:

            ratio_pn_list = np.linspace(ratio_pn_min, ratio_pn_max, n_ratio_pn)
            for ratio_pn in ratio_pn_list:
                # Copy and load ADEXL state of generated testbench
                # tb_sch.implement_design(impl_lib, top_cell_name = tb_name)
                # tb_obj = prj.configure_testbench(impl_lib, tb_name)
                tb_obj.set_parameter('vdd', vdd)
                tb_obj.set_parameter('vin_cm', vin_cm)
                tb_obj.set_parameter('vbig', vbig)
                tb_obj.set_parameter('vamp', vamp)
                tb_obj.set_parameter('vin_off', vin_off)
                tb_obj.set_parameter('cff', cff)
                tb_obj.set_parameter('tper', tper)
                tb_obj.set_parameter('tr', tr)
                tb_obj.set_parameter('tsu', tsu)

                nfpc = 4
                nfd = scale * ratio
                nft = nfd
                nfn = scale
                nfp = ratio_pn * nfn

                tb_obj.set_parameter('nfpc', nfpc)
                tb_obj.set_parameter('nfd', nfd)
                tb_obj.set_parameter('nft', nft)
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

                vod_vip_od = results['vod_vip_od']
                vod_vim_od = results['vod_vim_od']
                vod_vip_os = results['vod_vip_os']
                vod_vim_os = results['vod_vim_os']
                power = results['pavg']

                #
                nch_op_info = nch_db.query(vgs = vin_cm, vds = vdd/2, vbs = 0)
                cgg = nch_op_info['cgg'] * scale * ratio
                #

                design = dict(
                    nfpc = nfpc,
                    nfd = nfd,
                    nft = nft,
                    nfn = nfn,
                    nfp = nfp,
                    scale = scale,
                    ratio = ratio,
                    ratio_pn = ratio_pn,
                    Vodp_od = vod_vip_od,
                    Vodm_od = vod_vim_od,
                    Vodp_os = vod_vip_os,
                    Vodm_os = vod_vim_os,
                    Power = power,
                    Cgg = cgg
                    )
                pprint.pprint(design)

                if vod_vip_od >= vmin and vod_vim_od <= -vmin:
                    if (cyield != 0 and vod_vip_os >= vmin and vod_vim_os <= -vmin) or cyield == 0:
                        if power < min_power:
                            best_design = design
                            min_power = power
                        ratio_iter.up()
                ratio_iter.down()

    pprint.pprint(best_design)
    return


def run_main():
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('Creating BAG project')
        bprj = BagProject()
    else:
        print('Loading BAG project')
        bprj = local_dict['bprj']

    # pmos_spec = 'specs_mos_char/pch_w0d5_90n.yaml'
    nmos_spec = 'specs_mos_char/nch_w0d5_90n.yaml'
    intent = 'lvt'
    interp_method = 'linear'
    sim_env = 'tt'

    # pch_db = get_db(pmos_spec, intent, interp_method = interp_method, sim_env = sim_env)
    nch_db = get_db(nmos_spec, intent, interp_method = interp_method, sim_env = sim_env)

    specs = dict(
        # sim_env = sim_env,
        nch_db = nch_db,
        # vgs_res = 5e-3,
        vdd = 1.2,
        vin_cm = 0.6,
        vbig = 0.8,
        vamp = 20e-3, # 20
        vin_off = 25e-3, # 25
        vmin = 800e-3,
        cff = 5e-15, # 5
        tper = 120e-12, # 120
        tr = 20e-12,
        tsu = 30e-12,
        cyield = 0.9999, # 0.9999
        scale_min = 1, # 3, 3.86
        scale_max = 20,
        n_scale = 20,
        ratio_min = 1, # 7.6, 3.78
        ratio_max = 20,
        n_ratio = 20,
        ratio_pn_min = 0.4, # 0.4
        ratio_pn_max = 0.4,
        n_ratio_pn = 1
        )

    design_strong_arm(specs)


if __name__ == '__main__':
    run_main()
