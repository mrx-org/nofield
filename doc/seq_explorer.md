# General Functionality

## 1.Sequence collecting from different sources
Using a JSON file standard to register different file sources like
remote_file, github_folder, built-in, and modules like mrseq 
their individual dependences are stored in the JSON source register.
See [`pypulseq/sources_config.py`](../pypulseq/sources_config.py) for the initial source configuration. This file can be temporarily altered during the session.


## 2. Ability of refinement of these files with same 
all registered files can be refined and stored in the current session und "User Refined", dependencies are also tracked via a mini toml at the top of these files. Files can be executed and overwritten.


## 3. Inspect and adjust of Params of seq_funcs




## 4. Plotting.
We currently use matplotlib (mpl) for plotting. plots appear somehwer, are fetched and then put to the right possition.
same for their UI buttons. We have some experimental faster plots using line collections and coarser rasters.




