# Klipper plugin with helper commands for probe
#
# Copyright (C) 2024 Vladislav Zasetskii <vlzaseckiy@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
from extras.z_calibration import CalibrationState

class ProbeHoming:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command(
            'PROBE_AUTOCALIBRATE', self.cmd_PROBE_AUTOCALIBRATE,
            desc=self.cmd_PROBE_AUTOCALIBRATE_help
        )
        self.gcode.register_command(
            'APPLY_PROBE_OFFSET', self.cmd_APPLY_PROBE_OFFSET,
            desc=self.cmd_APPLY_PROBE_OFFSET_help
        )

    cmd_PROBE_AUTOCALIBRATE_help = (
        "Calibrate the probe's z_offset automatically")
    def cmd_PROBE_AUTOCALIBRATE(self, gcmd):
        z_calibration_helper = self.printer.lookup_object('z_calibration')
        nozzle_site = z_calibration_helper._get_nozzle_site(gcmd)
        switch_site = z_calibration_helper._get_switch_site(gcmd, nozzle_site)
        switch_offset = z_calibration_helper._get_switch_offset(gcmd)
        state = ProbeCalibrationState(z_calibration_helper, gcmd)
        state.probe_autocalibrate(nozzle_site, switch_site, switch_offset)

    cmd_APPLY_PROBE_OFFSET_help = "Apply the probe z-offset to the current Z position"
    def cmd_APPLY_PROBE_OFFSET(self, gcmd):
        probe = self.printer.lookup_object('probe')
        toolhead = self.printer.lookup_object('toolhead')
        z_calibration_helper = self.printer.lookup_object('z_calibration')
        current_z = toolhead.get_position()[2]
        probe_z_offset = probe.get_offsets()[2]
        switch_offset = z_calibration_helper._get_switch_offset(gcmd)
        new_z = current_z + probe_z_offset - switch_offset
        gcmd.respond_info(
            f"Current Z: {current_z} + probe z_offset: {probe_z_offset}"
            f" - switch_offset: {switch_offset} = new Z: {new_z}")
        self.gcode.run_script_from_command(f"SET_KINEMATIC_POSITION Z={new_z}")


class ProbeCalibrationState(CalibrationState):

    def probe_autocalibrate(self, nozzle_site, switch_site, switch_offset):
        # do the start preparations
        self.helper.start_gcode.run_gcode_from_command()
        try:
            # probe the nozzle
            nozzle_zero = self._probe_on_site(self.z_endstop,
                                              nozzle_site,
                                              check_probe=False,
                                              split_xy=True,
                                              wiggle=True)
            # execute switch gcode
            self.helper.switch_gcode.run_gcode_from_command()
            # probe switch body
            switch_zero = self._probe_on_site(self.z_endstop,
                                              switch_site,
                                              check_probe=True)
            z_offset = switch_zero + switch_offset - nozzle_zero
            self.gcode.respond_info(
                f"Switch zero: {switch_zero} + switch offset: {switch_offset} "
                f"- nozzle zero: {nozzle_zero} = probe z_offset: {z_offset}")
            self.gcode.respond_info(
                "probe_autocalibrate: z_offset: %.3f\n"
                "The SAVE_CONFIG command will update the printer config file\n"
                "with the above and restart the printer." % (z_offset))
            configfile = self.helper.printer.lookup_object('configfile')
            configfile.set(
                section='probe',
                option='z_offset',
                value="%.3f" % (z_offset,)
            )
        finally:
            # execute end gcode
            self.helper.end_gcode.run_gcode_from_command()


def load_config(config):
    return ProbeHoming(config)
