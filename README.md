# Valencia_Traffic_Lab
Visualization project for a subject from UPV-Data Science degree. Simulate and analyse traffic flow when closing and reopening streets in Valencia.

## Data
All data has been taken from https://github.com/ceferra/estat_trafic_VLC and treated with the `data_extractor.ipynb` file.

## Run
To execute this project on your machine you should:

* Create a virtual environment and install the requirements from the `requirements.txt` file
~~~bash
python -m venv venv app.py
~~~
~~~bash
source venv/bin/activate
~~~
~~~bash
pip install -r requirements.txt
~~~
* Download all zip files from the repo above mentioned, then run the code in the `data_extractor.ipynb` notebook changing the directory paths to yours.
* Run the app.py file with python to test locally or use Gunicorn to allow concurrency and deploy on a server.

### With python:

~~~bash
python3 app.py
~~~

### With Gunicorn:
~~~bash
gunicorn app:app
~~~

## Project

This project is developed for a subject deliverable in the UPV-Data Science degree, by [Hemma Povacz](https://www.github.com/hemmapovacz) and [Nadal Bardisa Quintero](https://www.github.com/NadalBQ)
