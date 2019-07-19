from six import string_types
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from functools import partial

from .stimulus_analysis import StimulusAnalysis
from .stimulus_analysis import osi, deg2rad


class StaticGratings(StimulusAnalysis):
    """
    A class for computing single-unit metrics from the static gratings stimulus of an ecephys session NWB file.

    To use, pass in a EcephysSession object::
        session = EcephysSession.from_nwb_path('/path/to/my.nwb')
        sg_analysis = StaticGratings(session)

    or, alternatively, pass in the file path::
        sg_analysis = StaticGratings('/path/to/my.nwb')

    You can also pass in a unit filter dictionary which will only select units with certain properties. For example
    to get only those units which are on probe C and found in the VISp area::
        sg_analysis = StaticGratings(session, filter={'location': 'probeC', 'structure_acronym': 'VISp'})

    To get a table of the individual unit metrics ranked by unit ID::
        metrics_table_df = sg_analysis.metrics()

    """

    def __init__(self, ecephys_session, **kwargs):
        super(StaticGratings, self).__init__(ecephys_session, **kwargs)
        self._orivals = None
        self._number_ori = None
        self._sfvals = None
        self._number_sf = None
        self._phasevals = None
        self._number_phase = None
        self._response_events = None
        self._response_trials = None

        self._metrics = None

        self._col_ori = 'Ori'
        self._col_sf = 'SF'
        self._col_phase = 'Phase'
        self._trial_duration = 0.25
        self._module_name = 'Static Gratings'

        if self._params is not None:
            self._params = self._params['static_gratings']
            self._stimulus_key = self._params['stimulus_key']
        else:
            self._stimulus_key = 'static_gratings'

    @property
    def orivals(self):
        """ Array of grating orientation conditions """
        if self._orivals is None:
            self._get_stim_table_stats()

        return self._orivals

    @property
    def number_ori(self):
        """ Number of grating orientation conditions """
        if self._number_ori is None:
            self._get_stim_table_stats()

        return self._number_ori

    @property
    def sfvals(self):
        """ Array of grating spatial frequency conditions """
        if self._sfvals is None:
            self._get_stim_table_stats()

        return self._sfvals

    @property
    def number_sf(self):
        """ Number of grating orientation conditions """
        if self._number_sf is None:
            self._get_stim_table_stats()

        return self._number_sf

    @property
    def phasevals(self):
        """ Array of grating phase conditions """
        if self._phasevals is None:
            self._get_stim_table_stats()

        return self._phasevals

    @property
    def number_phase(self):
        """ Number of grating phase conditions """
        if self._number_phase is None:
            self._get_stim_table_stats()

        return self._number_phase

    @property
    def null_condition(self):
        """ Stimulus condition ID for null (blank) stimulus """
        return self.stimulus_conditions[self.stimulus_conditions[self._col_sf] == 'null'].index
    

    @property
    def METRICS_COLUMNS(self):
        return [('pref_sf_sg', np.float64), 
                ('pref_ori_sg', np.float64), 
                ('pref_phase_sg', np.float64),
                ('g_osi_sg', np.float64), 
                ('time_to_peak_sg', np.float64),
                ('firing_rate_sg', np.float64), 
                ('reliability_sg', np.float64),
                ('fano_sg', np.float64), 
                ('lifetime_sparseness_sg', np.float64), 
                ('run_pval_sg', np.float64),
                ('run_mod_sg', np.float64)]

    @property
    def metrics(self):
        if self._metrics is None:

            print('Calculating metrics for ' + self.name)

            unit_ids = self.unit_ids
            
            metrics_df = self.empty_metrics_table()

            metrics_df['pref_sf_sg'] = [self._get_pref_sf(unit) for unit in unit_ids]
            metrics_df['pref_ori_sg'] = [self._get_pref_ori(unit) for unit in unit_ids]
            metrics_df['pref_phase_sg'] = [self._get_pref_phase(unit) for unit in unit_ids]
            metrics_df['g_osi_sg'] = [self._get_osi(unit, metrics_df.loc[unit]['pref_sf_sg'], metrics_df.loc[unit]['pref_phase_sg']) for unit in unit_ids]
            metrics_df['time_to_peak_sg'] = [self.get_time_to_peak(unit, self.get_preferred_condition(unit)) for unit in unit_ids]  
            metrics_df['firing_rate_sg'] = [self.get_overall_firing_rate(unit) for unit in unit_ids]
            metrics_df['reliability_sg'] = [self.get_reliability(unit, self.get_preferred_condition(unit)) for unit in unit_ids]
            metrics_df['fano_sg'] = [self.get_fano_factor(unit, self.get_preferred_condition(unit)) for unit in unit_ids]
            metrics_df['lifetime_sparseness_sg'] = [self.get_lifetime_sparseness(unit) for unit in unit_ids]
            metrics_df.loc[:, ['run_pval_sg', 'run_mod_sg']] = \
                    [self.get_running_modulation(unit, self.get_preferred_condition(unit)) for unit in unit_ids]

            self._metrics = metrics_df

        return self._metrics

    def _get_stim_table_stats(self):

        """ Extract orientations, spatial frequencies, and phases from the stimulus table """

        self._orivals = np.sort(self.stimulus_conditions.loc[self.stimulus_conditions[self._col_ori] != 'null'][self._col_ori].unique())
        self._number_ori = len(self._orivals)

        self._sfvals = np.sort(self.stimulus_conditions.loc[self.stimulus_conditions[self._col_sf] != 'null'][self._col_sf].unique())
        self._number_sf = len(self._sfvals)

        self._phasevals = np.sort(self.stimulus_conditions.loc[self.stimulus_conditions[self._col_phase] != 'null'][self._col_phase].unique())
        self._number_sf = len(self._sfvals)


    def _get_pref_sf(self, unit_id):

        """ Calculate the preferred spatial frequency condition for a given unit

        Params:
        -------
        unit_id - unique ID for the unit of interest

        Returns:
        -------
        pref_sf - spatial frequency driving the maximal response

        """

        similar_conditions = [self.stimulus_conditions.index[self.stimulus_conditions[self._col_sf] == sf].tolist() for sf in self.sfvals]
        df = pd.DataFrame(index=self.sfvals,
                         data = {'spike_mean' : 
                                [self.conditionwise_statistics.loc[unit_id].loc[condition_inds]['spike_mean'].mean() for condition_inds in similar_conditions]
                             }
                         ).rename_axis(self._col_sf)

        return df.idxmax().iloc[0]


    def _get_pref_ori(self, unit_id):

        """ Calculate the preferred orientation condition for a given unit

        Params:
        -------
        unit_id - unique ID for the unit of interest

        Returns:
        -------
        pref_ori - stimulus orientation driving the maximal response

        """

        similar_conditions = [self.stimulus_conditions.index[self.stimulus_conditions[self._col_ori] == ori].tolist() for ori in self.orivals]
        df = pd.DataFrame(index=self.orivals,
                         data = {'spike_mean' : 
                                [self.conditionwise_statistics.loc[unit_id].loc[condition_inds]['spike_mean'].mean() for condition_inds in similar_conditions]
                             }
                         ).rename_axis(self._col_ori)

        return df.idxmax().iloc[0]


    def _get_pref_phase(self, unit_id):

        """ Calculate the preferred phase condition for a given unit

        Params:
        -------
        unit_id - unique ID for the unit of interest

        Returns:
        -------
        pref_phase - stimulus phase driving the maximal response

        """

        similar_conditions = [self.stimulus_conditions.index[self.stimulus_conditions[self._col_phase] == phase].tolist() for phase in self.phasevals]
        df = pd.DataFrame(index=self.phasevals,
                         data = {'spike_mean' : 
                                [self.conditionwise_statistics.loc[unit_id].loc[condition_inds]['spike_mean'].mean() for condition_inds in similar_conditions]
                             }
                         ).rename_axis(self._col_phase)

        return df.idxmax().iloc[0]
    

    def _get_osi(self, unit_id, pref_sf, pref_phase):
        """ Calculate the orientation selectivity for a given unit

        Params:
        -------
        unit_id - unique ID for the unit of interest
        pref_sf - preferred spatial frequency for this unit
        pref_phase - preferred phase for this unit

        Returns:
        -------
        osi - orientation selectivity value

        """

        orivals_rad = deg2rad(self.orivals).astype('complex128')
        
        condition_inds = self.stimulus_conditions[
                (self.stimulus_conditions[self._col_sf] == pref_sf) & \
                (self.stimulus_conditions[self._col_phase] == pref_phase)
                ].index.values
        df = self.conditionwise_statistics.loc[unit_id].loc[condition_inds]
        df = df.assign(Ori = self.stimulus_conditions.loc[df.index.values][self._col_ori])
        df = df.sort_values(by=['Ori'])

        tuning = np.array(df['spike_mean'].values).astype('complex128')

        return osi(orivals_rad, tuning)


def fit_sf_tuning(sf_tuning_responses, sf_values, pref_sf_index):
    """Performs gaussian or exponential fit on the spatial frequency tuning curve at preferred orientation/phase for
    a given cell.

    :param sf_tuning_responses: An array of len N, with each value the (averaged) response of a cell at a given spatial
        freq. stimulus.
    :param sf_values: An array of len N, with each value the spatial freq. of the stimulus (corresponding to
        sf_tuning_response).
    :param pref_sf_index: The pre-determined prefered spatial frequency (sf_values index) of the cell.
    :return: index for the preferred sf from the curve fit, prefered sf from the curve fit, low cutoff sf from the
        curve fit, high cutoff sf from the curve fit
    """
    fit_sf_ind = np.NaN
    fit_sf = np.NaN
    sf_low_cutoff = np.NaN
    sf_high_cutoff = np.NaN
    if pref_sf_index in range(1, len(sf_values)-1):
        # If the prefered spatial freq is an interior case try to fit the tunning curve with a gaussian.
        try:
            popt, pcov = curve_fit(gauss_function, np.arange(len(sf_values)), sf_tuning_responses, p0=[np.amax(sf_tuning_responses),
                                                                                      pref_sf_index, 1.], maxfev=2000)
            sf_prediction = gauss_function(np.arange(0., 4.1, 0.1), *popt)
            fit_sf_ind = popt[1]
            fit_sf = 0.02*np.power(2, popt[1])
            low_cut_ind = np.abs(sf_prediction-(sf_prediction.max()/2.))[:sf_prediction.argmax()].argmin()
            high_cut_ind = np.abs(sf_prediction-(sf_prediction.max()/2.))[sf_prediction.argmax():].argmin() + sf_prediction.argmax()
            if low_cut_ind > 0:
                low_cutoff = np.arange(0, 4.1, 0.1)[low_cut_ind]
                sf_low_cutoff = 0.02*np.power(2, low_cutoff)
            elif high_cut_ind < 4:
                high_cutoff = np.arange(0, 4.1, 0.1)[high_cut_ind]
                sf_high_cutoff = 0.02*np.power(2, high_cutoff)
        except Exception as e:
            pass
    else:
        # If the prefered spatial freq is a boundary value try to fit the tunning curve with an exponential
        fit_sf_ind = pref_sf_index
        fit_sf = sf_values[pref_sf_index]
        try:
            popt, pcov = curve_fit(exp_function, np.arange(len(sf_values)), sf_tuning_responses,
                                   p0=[np.amax(sf_tuning_responses), 2., np.amin(sf_tuning_responses)], maxfev=2000)
            sf_prediction = exp_function(np.arange(0., 4.1, 0.1), *popt)
            if pref_sf_index == 0:
                high_cut_ind = np.abs(sf_prediction-(sf_prediction.max()/2.))[sf_prediction.argmax():].argmin()+sf_prediction.argmax()
                high_cutoff = np.arange(0, 4.1, 0.1)[high_cut_ind]
                sf_high_cutoff = 0.02*np.power(2, high_cutoff)
            else:
                low_cut_ind = np.abs(sf_prediction-(sf_prediction.max()/2.))[:sf_prediction.argmax()].argmin()
                low_cutoff = np.arange(0, 4.1, 0.1)[low_cut_ind]
                sf_low_cutoff = 0.02*np.power(2, low_cutoff)
        except Exception as e:
            pass

    return fit_sf_ind, fit_sf, sf_low_cutoff, sf_high_cutoff


def get_sfdi(sf_tuning_responses, mean_sweeps_trials, bias=5):
    """Computes spatial frequency discrimination index for cell

    :param sf_tuning_responses: sf_tuning_responses: An array of len N, with each value the (averaged) response of a
        cell at a given spatial freq. stimulus.
    :param mean_sweeps_trials: The set of events (spikes) across all trials of varying
    :param bias:
    :return: The sfdi value (float)
    """
    trial_mean = mean_sweeps_trials.mean()
    sse_part = np.sqrt(np.sum((mean_sweeps_trials - trial_mean)**2) / (len(mean_sweeps_trials) - bias))
    return (np.ptp(sf_tuning_responses)) / (np.ptp(sf_tuning_responses) + 2 * sse_part)


def gauss_function(x, a, x0, sigma):
    return a*np.exp(-(x-x0)**2/(2*sigma**2))


def exp_function(x, a, b, c):
    return a*np.exp(-b*x)+c
