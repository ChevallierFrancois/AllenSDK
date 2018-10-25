import sys
import matplotlib.pyplot as plt
import numpy as np
import icephys_api
import pandas as pd

DEFAULT_NWB2_FILE_NAME ="/allen/aibs/technology/sergeyg/ephys_pipeline/nwb_conversion/nwb2/Npr3-IRES2-CreSst-IRES-FlpOAi65-401243.04.01.01_ver2.nwb"


def plot_sweeps(nwbfile, sweep_table,
                xlim=[0,5],
                acquisition_trace_offset = None,
                stimulus_trace_offset = None):

    fig, ax = plt.subplots(1, 2, figsize=(10, 7))

    trace_ix = 0
    for sweep_name, sweep_info in sweep_table.iterrows():

        acquisition = nwbfile.get_acquisition(sweep_name)
        stimulus = nwbfile.get_stimulus(sweep_name)

        acquisition_data = acquisition.data
        stimulus_data = stimulus.data

        t_acq = np.arange(0,len(acquisition_data))/acquisition.rate
        t_stm = np.arange(0,len(stimulus_data))/stimulus.rate

        if stimulus_trace_offset is None:
            stimulus_trace_offset = -np.max(np.abs(stimulus_data))

        if acquisition_trace_offset is None:
            acquisition_trace_offset = -np.max(np.abs(acquisition_data))


        acquisition_offset = trace_ix * acquisition_trace_offset
        acquisition_data += acquisition_offset

        stimulus_offset = trace_ix * stimulus_trace_offset
        stimulus_data += stimulus_offset

        ax[0].plot(t_stm, stimulus_data)
        ax[0].set_xlabel('time (s)')
        ax[0].text(t_stm[-1]*0.5, stimulus_offset, " %s " % sweep_name, fontsize=10)
        ax[0].set_title("Stimulus (%4.0e*%s)" % (stimulus.conversion, stimulus.unit))
        ax[0].set_xlim(t_stm[0],t_stm[-1])

        ax[1].plot(t_acq,acquisition_data)
        ax[1].set_xlabel('time (s)')
        ax[1].set_title("Acquisition (%4.0e*%s)" % (acquisition.conversion,acquisition.unit))
        ax[1].set_xlim(t_acq[0],t_acq[-1])
        ax[1].text(t_stm[-1]*0.5, acquisition_offset, " %s" % sweep_name, fontsize=10)

        trace_ix+=1

    fig.suptitle("stimulus description: "+sweep_info["stimulus_description"], fontsize=18)
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])


def build_sweep_table(nwbfile):
    """

    Parameters
    ----------
    nwbfile: pynwb.NWBFile Class
        object containing timeseries data

    Returns
    -------
    sweep_table: pandas DF
        table of sweep properties
    """

    sweep_names = nwbfile.acquisition.keys()
    sweep_info = {}

    for sweep_name in sweep_names:

        ts = nwbfile.get_acquisition(sweep_name)
        sweep_info[sweep_name] = {
            "stimulus_description":ts.stimulus_description,
        }

    sweep_table = pd.DataFrame.from_dict(sweep_info, orient="index")
    sweep_table.index.name = 'sweep_name'
    return sweep_table




def main():

    """
    # Usage:
    $ python plot_icephys_nwb2.py NWB2_FILE_NAME

    """
    if len(sys.argv) == 1:
        sys.argv.append(DEFAULT_NWB2_FILE_NAME)

    nwb2_file_name = sys.argv[1]

    nwbfile = icephys_api.load_nwb2_file(nwb2_file_name)

    sweep_table = build_sweep_table(nwbfile)

    for name, sweep_group_table in sweep_table.groupby("stimulus_description"):
        plot_sweeps(nwbfile,sweep_group_table)

    plt.show()


if __name__ == "__main__": main()
