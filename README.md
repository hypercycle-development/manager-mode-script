# Manager mode script - Freelancing node

WIP: Describe the script goal

## Installation

### Setting Up the Virtual Environment

It is recommended to use a virtual environment to manage dependencies for this project. A virtual environment ensures isolation and avoids conflicts with global Python packages. You will need Python installed to create and run the environment.

You can use one of the following Python modules to create a virtual environment:

#### Using venv (comes with Python)

```bash
python -m venv .venv
```

#### Using virtualenv

```bash
python -m virtualenv .venv
```

Both commands create a virtual environment in a folder named `.venv`. While the folder can have a different name, `.venv` is a widely accepted convention.

### Activating the Virtual Environment

To activate the virtual environment:

```bash
source .venv/bin/activate
```

>**NOTE**: If you used a folder name other than .venv, adjust the path accordingly.

### Checking the Active Virtual Environment

To ensure you are using the correct virtual environment, run the following command:

```bash
which python
```

The output should point to this project’s virtual environment, for example:

```bash
/home/user/projects/manager-mode-script/.venv/bin/python
```

### Upgrading pip (Optional)

Upgrading pip before installing packages can prevent potential errors:

```bash
python -m pip install --upgrade pip
```

>**NOTE**: This will only upgrade pip within the virtual environment.

### Installing Dependencies

Once the virtual environment is activated, install the required dependencies from requirements.txt:

```bash
pip install -r requirements.txt
```

After completing these steps, the environment is ready to run the script

---
