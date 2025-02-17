import gym
from gym import spaces

import numpy as np
import pandas as pd 
import random

from gym_microgrid.envs.utils import price_signal
from gym_microgrid.envs.agents import *
from gym_microgrid.envs.reward import Reward
from gym_socialgame.envs.buffers import GaussianBuffer
from ray.rllib.env.multi_agent_env import make_multi_agent, MultiAgentEnv #from ray-project


from pymgrid import MicrogridGenerator as mg


    """perhaps think of using Tianshou instead of RLLib? https://tianshou.readthedocs.io/en/latest/tutorials/tictactoe.html#train-an-marl-agent
    
    Note: Tried a lot of different approaches, including
    1.discrete space and hardcoding lookup table
    2.hardcoding multiagent environment
    3.using from multiagent.core import World, Agent, Landmark, and using Scenarios
    4. Tianshou
    5. adversarial RL
    However, even though all of them were pretty detailed, they did not
    seem to work well with the pre-existing code in this repo, in terms of the continuous space, tuning parameters, and some were deprecated etc. Please test if the current
    rllib multiagent env setup works. If not, or if Lucas's
    implementation doesn't work either, will try to overhaul existing
    conditions of the agent and action space and use one of the libraries listed above (have some code for each)
    
    If multiagent RL working, then connecting prosumer microgrids not
    needed. Otherwise attempt (1) DQN multiagent RL--challenging, wasn't
    able to find a solution to this, but added the DQN algo to stablebaselines (2) generate microgrids--doesn't PPO
    ready do this? How to separate self into 2 sep microgrid environments
    with at least 1 distinct property--needs discussion before code? Tried (1) using pymgrid to generate microgrids"""
    
    """" Part of code to be deleted
    def MultiAgentEnv(
    
    def __init__(self,
    action_space_string = "continuous",
    response_type_string = "l",
    number_of_participants = 10,
    one_day = 0,
    energy_in_state = False,
    day_of_week = False,
    pricing_type="TOU",
    reward_function = "market_solving",
    manual_tou_magnitude=None,
    complex_batt_pv_scenario=1,
    exp_name = None,
    two_price_state = False,
    smirl_weight=None,
    observation_callback=None,
    info_callback=None,
    reset_callback=None,
    reward_callback=None,
    done_callback=None,
    shared_viewer=True): #change callback values above while training model. Otherwise use CustomCallbacks already in the CustomCallbacks file

        #configure spaces
        self.action_space = []
        self.observation_space = []
        
        #callbacks for RL: set of functions to be applied at given stages of the training procedure. Understand internal states and statistics of the model during training
        self.reset_callback = reset_callback
        self.reward_callback = reward_callback
        self.observation_callback = observation_callback
        self.info_callback = info_callback
        self.done_callback = done_callback
        
        # environment parameters
        self.discrete_action_input = False
        # if true, even the action is continuous, action will be performed discretely
        self.force_discrete_action = world.discrete_action if hasattr(world, 'discrete_action') else False
        # if true, every agent has the same reward
        self.shared_reward = world.collaborative if hasattr(world, 'collaborative') else False
        self.time = 0
                
"""


####### original

class MicrogridEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self,
        action_space_string = "continuous",
        response_type_string = "l",
        number_of_participants = 10,
        one_day = 0,
        energy_in_state = False,
        day_of_week = False,
        pricing_type="TOU",
        reward_function = "market_solving",
        manual_tou_magnitude=None,
        complex_batt_pv_scenario=1,
        exp_name = None,
        two_price_state = False,
        smirl_weight=None
        ):

        """
        MicrogridEnv for an agent determining incentives in a social game.

        Note: One-step trajectory (i.e. agent submits a 24-dim vector containing transactive price for each hour of each day.
            Then, environment advances one-day and agent is told that the episode has finished.)

        Args:
            action_space_string: (String) either "continuous" or "multidiscrete"
            response_type_string: (String) either "t", "s", "l" , denoting whether the office's response function is threshold, sinusoidal, or linear
            number_of_participants: (Int) denoting the number of players in the social game (must be > 0 and < 20)
            one_day: (Int) in range [-1,365] denoting which fixed day to train on .
                    Note: -1 = Random Day, 0 = Train over entire Yr, [1,365] = Day of the Year
            energy_in_state: (Boolean) denoting whether (or not) to include the previous day's energy consumption within the state
            yesterday_in_state: (Boolean) denoting whether (or not) to append yesterday's price signal to the state
            manual_tou_magnitude: (Float>1) The relative magnitude of the TOU pricing to the regular pricing

        """
        super(MicrogridEnv, self).__init__()

        #Verify that inputs are valid
        self.check_valid_init_inputs(
            action_space_string,
            response_type_string,
            number_of_participants,
            one_day,
            energy_in_state,
        )

        #Assigning Instance Variables
        self.action_space_string = action_space_string
        self.response_type_string = response_type_string
        self.number_of_participants = number_of_participants
        self.one_day = self._find_one_day(one_day)
        self.energy_in_state = energy_in_state
        self.two_price_state = two_price_state
        self.reward_function = reward_function
        self.manual_tou_magnitude = manual_tou_magnitude
        self.complex_batt_pv_scenario = complex_batt_pv_scenario

        self.smirl_weight = smirl_weight
        self.use_smirl = smirl_weight > 0 if smirl_weight else False
        self.hours_in_day = 10
        self.last_smirl_reward = None
        self.last_energy_reward = None

        self.day = 0
        self.days_of_week = [0, 1, 2, 3, 4]
        self.day_of_week_flag = day_of_week
        self.day_of_week = self.days_of_week[self.day % 5]
        self.day_length = 24

        #Create Observation Space (aka State Space)
        self.observation_space = self._create_observation_space()

        self.pricing_type = "real_time_pricing" if pricing_type.upper() == "RTP" else "time_of_use"

        self.buyprices_grid, self.sellprices_grid = self._get_prices()
        # self.prices = self.buyprices_grid #Initialise to buyprices_grid
        self.generation = self._get_generation()

        #Day corresponds to day # of the yr

        #Cur_iter counts length of trajectory for current step (i.e. cur_iter = i^th hour in a 10-hour trajectory)
        #For our case cur_iter just flips between 0-1 (b/c 1-step trajectory)
        self.curr_iter = 0
        self.total_iter = 0

        #Create Action Space
        self.action_length = 72 # TODO: Check with Utkarsha
        self.action_subspace = 3
        self.action_space = self._create_action_space()

        #Create Prosumers
        self.prosumer_dict = self._create_agents()

        #TODO: Check initialization of prev_energy
        self.prev_energy = np.zeros(self.day_length)

        if self.use_smirl:
            self.buffer = GaussianBuffer(self.action_length)

        self.iteration = 0

        print("\n Microgrid Environment Initialized! Have Fun! \n")

    def _find_one_day(self, one_day: int):
        """
        Purpose: Helper function to find one_day to train on (if applicable)

        Args:
            One_day: (Int) in range [-1,365]

        Returns:
            0 if one_day = 0
            one_day if one_day in range [1,365]
            random_number(1,365) if one_day = -1
        """

        return one_day if one_day != -1 else np.random.randint(0, high=365)

    def _create_observation_space(self):
        """
        Purpose: Returns the observation space.
        State space includes:
            Previous day's net total energy consumption (24 dim)
            Future (current) day's renewable generation prediction (24 dim)
            Future (current) day's ToU buy prices from utility (24 dim)
        
        Args:
            None

        Returns:
            State Space for environment based on action_space_str
        """

        return spaces.Box(low=-np.inf, high=np.inf, shape=(72,), dtype=np.float32)

    def _create_action_space(self):
        """
        Purpose: Return action space of type specified by self.action_space_string

        Args:
            None

        Returns:
            Action Space for environment based on action_space_str

        Note: Multidiscrete refers to a 10-dim vector where each action {0,1,2} represents Low, Medium, High points respectively.
        We pose this option to test whether simplifying the action-space helps the agent.
        """


        #Making a symmetric, continuous space to help learning for continuous control (suggested in StableBaselines doc.)
        if not self.two_price_state:
            return spaces.Box(low=-1, high=1, shape=(self.day_length,), dtype=np.float32)
        else: 
            return spaces.Box(low = -1, high = 1, shape = (2 * self.day_length, ), dtype = np.float32)

        

    def _create_agents(self):
        """
        Purpose: Create the prosumers in the local energy market. 
        We create a market with n players, where n = self.number_of_participants

        Args:
            None

        Returns:
              prosumer_dict: Dictionary of prosumers

        """
        prosumer_dict = {}

        # Manually set battery numbers and PV sizes

        ## large and constant batt and PV
        if self.complex_batt_pv_scenario == 1:
            battery_nums = [50]*self.number_of_participants
            pvsizes = [100]*self.number_of_participants

        ## small PV sizes
        elif self.complex_batt_pv_scenario ==2: 
            pvsizes = [ 0, 10, 100, 10, 0, 0, 0, 55, 10, 10 ]
            battery_nums = [ 0, 0, 50, 30, 50, 0, 0, 10, 40, 50 ]

        ## medium PV sizes and different
        elif self.complex_batt_pv_scenario == 3:
            pvsizes = [ 70, 110, 400, 70, 30, 0, 0, 55, 10, 20 ]
            battery_nums = [ 0, 0, 150, 30, 50, 0, 0, 100, 40, 150]

        ## no batteries 
        elif self.complex_batt_pv_scenario == 4:
            pvsizes = [ 70, 110, 400, 70, 30, 0, 0, 55, 10, 20 ]
            battery_nums = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]
        
        # no solar 
        elif self.complex_batt_pv_scenario == 5:
            pvsizes = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]
            battery_nums = [ 0, 0, 150, 30, 50, 0, 0, 100, 40, 150 ]
        
        # nothing at all 
        elif self.complex_batt_pv_scenario == 6:
            pvsizes = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]
            battery_nums = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]

        # wrong number 
        else:
            print("you've inputted an incorrect scenario")
            raise AssertionError

        # Get energy from building_data.csv file,  each office building has readings in kWh. Interpolate to fill missing values
        df = pd.read_csv('building_data.csv').interpolate().fillna(0)
        building_names = df.columns[5:] # Skip first few columns 
        for i in range(len(building_names)):
            name = building_names[i]
            prosumer = Prosumer(name, np.squeeze(df[[name]].values), .001*np.squeeze(df[['PV (W)']].values), battery_num = battery_nums[i], pv_size = pvsizes[i])
            prosumer_dict[name] = prosumer

        return prosumer_dict

    def _get_generation(self):
        """
        Purpose: Get solar energy predictions for the entire year 

        Args:
            None

        Returns: Array containing solar generation predictions, where array[day_number] = renewable prediction for day_number 
        """

        yearlonggeneration = []

        # Read renewable generation from CSV file. Index starts at 5 am on Jan 1, make appropriate adjustments. For year 2012: it is a leap year
        # generation = pd.read_csv('/Users/utkarshapets/Documents/Research/Optimisation attempts/building_data.csv')[['PV (W)']]
        generation = np.squeeze(pd.read_csv('/home/tc/gym-microgrid/gym_microgrid/envs/building_data.csv')[['PV (W)']].values)
        for day in range(0, 365):
            yearlonggeneration.append(
                generation[day*self.day_length+19 : day*self.day_length+19+24]
            )
               
        return np.array(yearlonggeneration)

    def _get_prices(self):
        """
        Purpose: Get grid price signals for the entire year (PG&E commercial rates)

        Args:
            None

        Returns: Two arrays containing 365 price signals, where array[day_number] = grid_price for day_number 
        One each for buyprice and sellprice: sellprice set to be a fraction of buyprice

        """

        buy_prices = []
        sell_prices = []


        # Read PG&E price from CSV file. Index starts at 5 am on Jan 1, make appropriate adjustments. For year 2012: it is a leap year
        # price = pd.read_csv('/Users/utkarshapets/Documents/Research/Optimisation attempts/building_data.csv')[['Price( $ per kWh)']]
        price = np.squeeze(pd.read_csv('/home/tc/gym-microgrid/gym_microgrid/envs/building_data.csv')[['Price( $ per kWh)']].values)

        for day in range(0, 365):
            buyprice = price[day*self.day_length+19 : day*self.day_length+19+24]
            sellprice = 0.6*buyprice
            buy_prices.append(buyprice)
            sell_prices.append(sellprice)

        return buy_prices, sell_prices

    def _price_from_action(self, action):
        """
        Purpose: Convert agent actions that lie in [-1,1] into transactive price (conversion is for multidiscrete setting)

        Args:
            Action: 24-dim vector corresponding to action for each hour

        Returns: Price: 24-dim vector of transactive prices
        """
        
        # Continuous space is symmetric [-1,1], we map to -> [sellprice_grid,buyprice_grid] 
        day = self.day
        buyprice_grid = self.buyprices_grid[day]
        sellprice_grid = self.sellprices_grid[day]
        
        # -1 -> sellprice. 1 -> buyprice

        if not self.two_price_state:
            midpoint_price = (buyprice_grid + sellprice_grid)/2
            diff_grid = buyprice_grid - sellprice_grid
            scaled_diffs = np.multiply(action, diff_grid)/2 # Scale to fit difference at each hour
            price = scaled_diffs + midpoint_price
            return price

        else:
            midpoint_price = (buyprice_grid + sellprice_grid)/2
            diff_grid = buyprice_grid - sellprice_grid
            scaled_diffs_bp = np.multiply(action[0:24], diff_grid)/2 # Scale to fit difference at each hour
            scaled_diffs_sp = np.multiply(action[24:], diff_grid)/2 # Scale to fit difference at each hour
            buyprice = scaled_diffs_bp + midpoint_price
            sellprice = scaled_diffs_sp + midpoint_price
            return buyprice, sellprice


    def _simulate_humans(self, day, price):
        """
        Purpose: Gets energy consumption from players given action from agent
                 Price: transactive price set in day-ahead manner

        Args:
            Day: day of the year. Values allowed [0, 365)
            Price: 24-dim vector corresponding to a price for each hour of the day

        Returns:
            Energy_consumption: Dictionary containing the energy usage by prosumer. Key 'Total': aggregate net energy consumption
        """

        energy_consumptions = {}
        total_consumption = np.zeros(24)

        for prosumer_name in self.prosumer_dict:

            #Get players response to agent's actions
            prosumer = self.prosumer_dict[prosumer_name]
            prosumer_demand = prosumer.get_response(day, price)
  
            #Calculate energy consumption by prosumer and in total (entire aggregation)
            energy_consumptions[prosumer_name] = prosumer_demand
            total_consumption += prosumer_demand


        energy_consumptions["Total"] = total_consumption 
        return energy_consumptions

    def _simulate_prosumers_twoprices(self, day, buyprice, sellprice):
        """
        Purpose: Gets energy consumption from players given action from agent
                 Price: transactive price set in day-ahead manner

        Args:
            Day: day of the year. Values allowed [0, 365)
            Price: 2 24-dim vector corresponding to a price for each hour of the day

        Returns:
            Energy_consumption: Dictionary containing the energy usage by prosumer. Key 'Total': aggregate net energy consumption
        """

        energy_consumptions = {}
        total_consumption = np.zeros(24)

        for prosumer_name in self.prosumer_dict:
            
            #Get players response to agent's actions
            prosumer = self.prosumer_dict[prosumer_name]
            prosumer_demand = prosumer.get_response_twoprices(day, buyprice, sellprice)
  
            #Calculate energy consumption by prosumer and in total (entire aggregation)
            energy_consumptions[prosumer_name] = prosumer_demand
            total_consumption += prosumer_demand


        energy_consumptions["Total"] = total_consumption 
        return energy_consumptions

    def _get_reward(self, buyprice_grid, sellprice_grid, transactive_price, energy_consumptions):
        """
        Purpose: Compute reward given grid prices, transactive price set ahead of time, and energy consumption of the participants

        Args:
            buyprice_grid: price at which energy is bought from the utility (24 dim vector)
            sellprice_grid: price at which energy is sold to the utility by the RL agent (24 dim vector)
            transactive_price: price set by RL agent for local market in day ahead manner (24 dim vector)
            energy_consumptions: Dictionary containing energy usage by each prosumer, as well as the total

        Returns:
            Reward for RL agent (- |net money flow|): in order to get close to market equilibrium
        """

        total_consumption = energy_consumptions['Total']
        money_to_utility = np.dot(np.maximum(0, total_consumption), buyprice_grid) + np.dot(np.minimum(0, total_consumption), sellprice_grid)
        money_from_prosumers = np.dot(total_consumption, transactive_price)

        total_energy_reward = 0
        total_smirl_reward = 0

        if self.reward_function == "market_solving":
            total_energy_reward = - abs(money_from_prosumers - money_to_utility)
        elif self.reward_function =="profit_maximizing":
            total_energy_reward = money_from_prosumers - money_to_utility

        
        if self.use_smirl:
            smirl_rew = self.buffer.logprob(self._get_observation())
            total_smirl_reward = self.smirl_weight * np.clip(smirl_rew, -300, 300)

        self.last_smirl_reward = total_smirl_reward
        self.last_energy_reward = total_energy_reward

        return total_energy_reward + total_smirl_reward

    def _get_reward_twoprices(self, buyprice_grid, sellprice_grid, transactive_buyprice, transactive_sellprice, energy_consumptions):
        """
        Purpose: Compute reward given grid prices, transactive price set ahead of time, and energy consumption of the participants

        Args:
            buyprice_grid: price at which energy is bought from the utility (24 dim vector)
            sellprice_grid: price at which energy is sold to the utility by the RL agent (24 dim vector)
            transactive_buyprice: price set by RL agent for local market in day ahead manner (24 dim vector)
            transactive_sellprice: price set by RL agent for local market in day ahead manner (24 dim vector)
            energy_consumptions: Dictionary containing energy usage by each prosumer, as well as the total

        Returns:
            Reward for RL agent (- |net money flow|): in order to get close to market equilibrium
        """

        total_consumption = energy_consumptions['Total']
        money_to_utility = np.dot(np.maximum(0, total_consumption), buyprice_grid) + np.dot(np.minimum(0, total_consumption), sellprice_grid)

        money_from_prosumers = 0
        for prosumerName in energy_consumptions:
            money_from_prosumers += (np.dot(np.maximum(0, energy_consumptions[prosumerName]), transactive_buyprice) + np.dot(np.minimum(0, energy_consumptions[prosumerName]), transactive_sellprice))

        total_reward = None
        if self.reward_function == "market_solving":
            total_reward = - abs(money_from_prosumers - money_to_utility)
        elif self.reward_function =="profit_maximizing":
            total_reward = money_from_prosumers - money_to_utility

        return total_reward



    def step(self, action):
        """
        Purpose: Takes a step in the environment

        Args:
            Action: 24 dim vector in [-1, 1]

        Returns:
            Observation: State for the next day
            Reward: Reward for said action
            Done: Whether or not the day is done (should always be True b/c of 1-step trajectory)
            Info: Other info (primarily for gym env based library compatibility)

        Exceptions:
            raises AssertionError if action is not in the action space
        """

        self.action = action

        if not self.action_space.contains(action):
            action = np.asarray(action)
            if self.action_space_string == 'continuous':
                action = np.clip(action, -1, 1)
                # TODO: ask Lucas about this
            else:
                print("wrong action_space_string")
                raise AssertionError

        # prev_price = self.prices[(self.day)]
        self.day = (self.day + 1) % 365 
        self.curr_iter += 1
        self.total_iter += 1

        done = self.curr_iter > 0

        if not self.two_price_state:
            price = self._price_from_action(action)
            self.price = price

            energy_consumptions = self._simulate_humans(day = self.day, price = price)
            self.prev_energy = energy_consumptions["Total"]

            observation = self._get_observation()
        
            buyprice_grid = self.buyprices_grid[self.day]
            sellprice_grid = self.sellprices_grid[self.day]
            reward = self._get_reward(buyprice_grid, sellprice_grid, price, energy_consumptions)

            self.iteration += 1

        else: 

            buyprice, sellprice = self._price_from_action(action)
            # self.price = price

            energy_consumptions = self._simulate_prosumers_twoprices(
                day = self.day, 
                buyprice = buyprice, 
                sellprice = sellprice)

            self.prev_energy = energy_consumptions["Total"]

            observation = self._get_observation()
        
            buyprice_grid = self.buyprices_grid[self.day]
            sellprice_grid = self.sellprices_grid[self.day]
            reward = self._get_reward_twoprices(buyprice_grid, sellprice_grid, buyprice, sellprice, energy_consumptions)
            
            self.iteration += 1

        if self.use_smirl:
            self.buffer.add(observation)

        info = {}
        return observation, reward, done, info

    def _get_observation(self):
    
        prev_energy = self.prev_energy
        generation_tomorrow = self.generation[(self.day + 1)%365] 
        buyprice_grid_tomorrow = self.buyprices_grid[(self.day + 1)%365] 

        noise = np.random.normal(loc = 0, scale = 50, size = 24) ## TODO: get rid of this if not doing well
        generation_tomorrow_nonzero = (generation_tomorrow > abs(noise)) # when is generation non zero?
        generation_tomorrow += generation_tomorrow_nonzero* noise # Add in Gaussian noise when gen in non zero

        return np.concatenate(
            (prev_energy, generation_tomorrow, buyprice_grid_tomorrow)
            )
        

    def reset(self):
        """ Resets the environment on the current day """
        return self._get_observation()

    def render(self, mode='human'):
        pass

    def close(self):
        pass


    def check_valid_init_inputs(self, action_space_string: str, response_type_string: str, number_of_participants = 10,
                one_day = False, energy_in_state = False):

        """
        Purpose: Verify that all initialization variables are valid

        Args (from initialization):
            action_space_string: String either "continuous" or "discrete" ; Denotes the type of action space
            response_type_string: String either "t", "s", "l" , denoting whether the office's response function is threshold, sinusoidal, or linear
            number_of_participants: Int denoting the number of players in the social game (must be > 0 and < 20)
            one_day: Boolean denoting whether (or not) the environment is FIXED on ONE price signal
            energy_in_state: Boolean denoting whether (or not) to include the previous day's energy consumption within the state
            yesterday_in_state: Boolean denoting whether (or not) to append yesterday's price signal to the state

        Exceptions:
            Raises AssertionError if action_space_string is not a String or if it is not either "continuous", or "multidiscrete"
            Raises AssertionError if response_type_string is not a String or it is is not either "t","s","l"
            Raises AssertionError if number_of_participants is not an integer, is less than 1,  or greater than 20 (upper bound set arbitrarily for comp. purposes).
            Raises AssertionError if any of {one_day, energy_in_state, yesterday_in_state} is not a Boolean
        """

        #Checking that action_space_string is valid
        assert isinstance(action_space_string, str), "action_space_str is not of type String. Instead got type {}".format(type(action_space_string))
        action_space_string = action_space_string.lower()
        assert action_space_string in ["continuous", "multidiscrete", "continuous_normalized"], "action_space_str is not continuous or discrete. Instead got value {}".format(action_space_string)

        #Checking that response_type_string is valid
        assert isinstance(response_type_string, str), "Variable response_type_string should be of type String. Instead got type {}".format(type(response_type_string))
        response_type_string = response_type_string.lower()
        assert response_type_string in ["t", "s", "l"], "Variable response_type_string should be either t, s, l. Instead got value {}".format(response_type_string)


        #Checking that number_of_participants is valid
        assert isinstance(number_of_participants, int), "Variable number_of_participants is not of type Integer. Instead got type {}".format(type(number_of_participants))
        assert number_of_participants > 0, "Variable number_of_participants should be atleast 1, got number_of_participants = {}".format(number_of_participants)
        assert number_of_participants <= 20, "Variable number_of_participants should not be greater than 20, got number_of_participants = {}".format(number_of_participants)

        #Checking that one_day is valid
        assert isinstance(one_day, int), "Variable one_day is not of type Int. Instead got type {}".format(type(one_day))
        assert 366 > one_day and one_day > -2, "Variable one_day out of range [-1,365]. Got one_day = {}".format(one_day)

        #Checking that energy_in_state is valid
        assert isinstance(energy_in_state, bool), "Variable one_day is not of type Boolean. Instead got type {}".format(type(energy_in_state))

        print("all inputs valid")





class MicrogridEnvRLLib(MicrogridEnv):
    """ 
    Child Class of MicrogridEnv to support RLLib. 
    two_price_state and complex_batt_pv are specific params for the MicrogridEnv
    and differs from SocialGame.
    num_agents manually set to 3 so it can be accessed by make_multi_agent
    """
    
    def __init__(self, env_config):
        super().__init__(
            action_space_string = env_config["action_space_string"], 
            response_type_string = env_config["response_type_string"],
            number_of_participants = env_config["number_of_participants"],
            one_day = env_config["one_day"],
            energy_in_state = env_config["energy_in_state"],
            pricing_type=env_config["pricing_type"],
            reward_function = env_config["reward_function"],
            manual_tou_magnitude=env_config["manual_tou_magnitude"],
            smirl_weight=env_config["smirl_weight"], 
            complex_batt_pv_scenario=1, 
            two_price_state = False,
            num_agents = 3
        )
        print("Initialized RLLib child class for MicrogridEnv.")


MicrogridMultiAgent = make_multi_agent(lambda config: MicrogridEnvRLLib(config))


#generates 10 microgrids by default that can be used to compare to the MicrogridEnv microgrid. Not sure how to recognize differences or simulate multiple versions of MicrogridEnv
m_gen=mg.MicrogridGenerator()
m_gen.generate_microgrid()
