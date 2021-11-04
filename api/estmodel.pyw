#!/usr/bin/env python3

# Copyright (c) 2020-2021 Estonian Environment Agency

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from csv import writer
from datetime import date
from json import dump, dumps, load
from multiprocessing import Pipe, Process, freeze_support
from sys import executable
from tkinter import (BOTH, DISABLED, END, FALSE, NO, NORMAL, SE, YES,
                     BooleanVar, E, N, S, StringVar, Tk, Toplevel, W, X)
from tkinter.filedialog import asksaveasfilename
from tkinter.messagebox import showerror
from tkinter.ttk import (Button, Checkbutton, Combobox, Entry, Frame, Label,
                         Notebook, Progressbar, Scrollbar, Treeview)
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PARAMETERS = {
    "AOX": "Adsorbable organic halides",
    "BOD5": "5 day biochemical oxygen demand",
    "BOD7": "7 day biochemical oxygen demand",
    "CD": "Cadmium",
    "COD-CR": "Chemical oxygen demand (Cr)",
    "COD-MN": "Chemical oxygen demand (KMnO4)",
    "CR": "Chromium",
    "CU": "Copper",
    "HG": "Mercury",
    "NH4-N": "Ammonium nitrogen",
    "NI": "Nickel",
    "NO2-N": "Nitrite nitrogen",
    "NO23-N": "Nitrite nitrogen and nitrate nitrogen",
    "NO3-N": "Nitrate nitrogen",
    "OIL": "Oil",
    "PB": "Lead",
    "PO4-P": "Phosphate",
    "Q": "Flow",
    "SS": "Suspended solids",
    "TN": "Total nitrogen",
    "TOC": "Total organic carbon",
    "TP": "Total phosphorus",
    "ZN": "Zinc"
}

SERVICE_BASE_HREF = "https://estmodel.envir.ee"

SOURCES = {
    "arableland": "Arable lands",
    "forest": "Forests",
    "pasture": "Pastures",
    "peatland": "Peatlands",
    "point": "Point sources",
    "water": "Water surfaces",
    "wetland": "Wetlands",
    "other": "Other"
}


def find(*path, **qparams):
    url = SERVICE_BASE_HREF + "/" + "/".join(path)
    if qparams:
        qparams = {p.replace("_", "-"): v for p, v in qparams.items()}
        url += "?" + urlencode(qparams)
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"})) as response:
            results = load(response)
            if path[-1].endswith("estimates") or path[-1].endswith("measurements"):
                for result in results:
                    result["date"] = date.fromisoformat(result["date"])
                    result["parameter"] = result["parameter"].upper()
            return results
    except HTTPError as error:
        if error.code == 400:
            raise HTTPError(error.filename, error.code, error.read()
                            .decode("utf-8"), error.headers, error.fp) from None
        else:
            raise error


def run(estmodel):
    try:
        with urlopen(Request(SERVICE_BASE_HREF,
                             method="POST",
                             data=dumps(estmodel).encode("utf-8"),
                             headers={"Content-Type": "application/json"})) as response:
            return load(response)
    except HTTPError as error:
        if error.code == 400:
            raise HTTPError(error.filename, error.code, error.read()
                            .decode("utf-8"), error.headers, error.fp) from None
        else:
            raise error


def sumattr(catchment, source, property, parameter=None):
    result = 0.0
    if source == "point":
        for ps in catchment.get("pointSources", []):
            result += ps.get(property, 0.0)
            for e in ps.get("estimates", []):
                if e.get("parameter", "").upper() == parameter:
                    if property == "totalDischarge":
                        result += e.get("anthropogenicDischarge", 0.0)
                    else:
                        result += e.get(property, 0.0)
    else:
        for ds in catchment.get("diffuseSources", []):
            if (ds.get("type") or "other") == source:
                result += ds.get(property, 0.0)
                for e in ds.get("estimates", []):
                    if e.get("parameter", "").upper() == parameter:
                        if property == "totalDischarge":
                            result += e.get("naturalDischarge", 0.0)
                            result += e.get("anthropogenicDischarge", 0.0)
                            result += e.get("atmosphericDeposition", 0.0)
                        else:
                            result += e.get(property, 0.0)
    for sc in catchment.get("subcatchments", []):
        result += sumattr(sc, source, property, parameter)
    return result


class EstModelClient(Tk):

    def __init__(self):
        super().__init__()
        self.minsize(800, 600)
        self.title("EstModel")
        self.iconbitmap(default=executable)
        self.book = Notebook(self, padding=(0, 5, 0, 0))
        self.book.add(ModelFrame(self.book), text="Models")
        self.book.add(EstimateFrame(self.book), text="Estimates")
        self.book.add(MeasurementFrame(self.book), text="Measurements")
        self.book.pack(fill=BOTH, expand=YES)

    def report_callback_exception(self, exc, val, tb):
        showerror("Error", "Connection error")


class LoadingWindow(Toplevel):

    def __init__(self, master, process):
        super().__init__(master, padx=12, pady=12)
        self.minsize(300, 100)
        self.title("0% complete")
        self.process = process
        self.progress = Progressbar(self)
        self.progress.pack(expand=YES, fill=X)
        self.cancel_button = Button(self, text="Cancel", command=self.destroy)
        self.cancel_button.pack(anchor=SE)
        self.resizable(height=FALSE, width=FALSE)
        self.transient(master)
        self.grab_set()
        self.cancel_button.focus_set()
        self.process.start()
        self.master.after(100, self.step)

    def destroy(self):
        self.process.terminate()

    def step(self):
        if round(self.progress["value"]) < self.progress["maximum"]:
            while self.process.parent_connection.poll():
                self.progress["value"] += self.process.parent_connection.recv()
            self.title("{}% complete".format(round(self.progress["value"])))
        else:
            self.title("Writing data to file")
        if self.process.is_alive():
            self.master.after(100, self.step)
        else:
            super().destroy()
            self.process.close()


class MeasurementFrame(Frame):

    def __init__(self, master, parameters=PARAMETERS):
        super().__init__(master)
        self.book1 = Notebook(self, padding=(5, 5, 0, 0))
        self.book1.add(StationFrame(self.book1), text="Stations")
        self.book1.grid(row=0, column=0, sticky=N+S+E+W)
        self.book2 = Notebook(self, padding=(5, 5, 0, 0))
        self.book2.add(ParameterFrame(
            self.book2, parameters), text="Parameters")
        self.book2.grid(row=0, column=1, sticky=N+S+E+W)
        self.save_button = Button(self, text="Save...", command=self.save)
        self.save_button.grid(row=1, column=1, padx=5, pady=5, sticky=E)
        self.save_button.focus_set()
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def save(self):
        filename = asksaveasfilename(defaultextension=".csv",
                                     filetypes=[("CSV File", ".csv")])
        if not filename:
            return
        frame1 = self.nametowidget(self.book1.select())
        frame2 = self.nametowidget(self.book2.select())
        parameters = frame2.view.selection()
        if not parameters:
            parameters = frame2.view.get_children()
        stations = frame1.view.selection()
        if not stations:
            stations = frame1.view.get_children()
        LoadingWindow(self, MeasurementProcess(filename, stations, parameters,
                                               frame2.start_year.get(),
                                               frame2.end_year.get()))


class MeasurementProcess(Process):

    def __init__(self, filename, stations, parameters, start_year, end_year):
        super().__init__(daemon=True)
        self.filename = filename
        self.parent_connection, self.child_connection = Pipe(duplex=False)
        self.parameters = parameters
        self.stations = stations
        self.start_year = start_year
        self.end_year = end_year

    def run(self):
        rows = [[
            "Station code",
            "Station name",
            "Parameter code",
            "Parameter name",
            "Date",
            "Value",
            "LOD",
            "Unit",
            "Uncertainty"
        ]]
        for station_code, station_name in self.stations.items():
            for parameter_code, parameter_name in self.parameters.items():
                for measurement in find("stations", station_code, "measurements",
                                        start_year=self.start_year,
                                        end_year=self.end_year,
                                        parameter=parameter_code.lower()):
                    rows.append([
                        station_code,
                        station_name,
                        parameter_code,
                        parameter_name,
                        measurement["date"],
                        measurement["value"],
                        measurement["limit"],
                        measurement["unit"],
                        measurement["uncertainty"]])
                self.child_connection.send(100 / len(self.stations)
                                           / len(self.parameters))

        with open(self.filename, "w", newline="") as file:
            writer(file, delimiter=";").writerows(rows)


class ModelFrame(MeasurementFrame):

    def __init__(self, master, parameters={parameter: PARAMETERS[parameter]
                                           for parameter in ["TN", "TP"]}):
        super().__init__(master, parameters)
        self.book1.add(WaterbodyFrame(self.book1), text="River waterbodies")
        self.book1.add(RiverFrame(self.book1), text="Rivers")
        self.book1.add(DistrictFrame(self.book1), text="River basin districts")
        self.book1.add(CountryFrame(self.book1), text="Countries")
        frame2 = self.nametowidget(self.book2.select())
        frame2.time_step = StringVar(frame2)
        frame2.time_step_label = Label(frame2, text="Time step")
        frame2.time_step_label.grid(row=4, padx=5, pady=(16, 2), sticky=W)
        frame2.time_step_combobox = Combobox(frame2, state=DISABLED,
                                             textvariable=frame2.time_step,
                                             values=[
                                                 "Year",
                                                 "Quarter year",
                                                 "Month",
                                                 "Day"
                                             ])
        frame2.time_step_combobox.current(0)
        frame2.time_step_combobox.grid(row=5, padx=5)

    def save(self):
        filename = asksaveasfilename(defaultextension=".csv",
                                     filetypes=[("CSV File", ".csv"),
                                                ("JSON File", ".json")])
        if not filename:
            return
        frame1 = self.nametowidget(self.book1.select())
        frame2 = self.nametowidget(self.book2.select())
        parameters = frame2.view.selection()
        if not parameters:
            parameters = frame2.view.get_children()
        catchments = frame1.view.selection()
        if not catchments:
            catchments = frame1.view.get_children()
        LoadingWindow(self, ModelProcess(filename, catchments,
                                         frame1.collection,
                                         parameters,
                                         frame2.start_year.get(),
                                         frame2.end_year.get()))


class ModelProcess(Process):

    def __init__(self, filename, catchments, catchments_type,
                 parameters, start_year, end_year):
        super().__init__(daemon=True)
        self.filename = filename
        self.parent_connection, self.child_connection = Pipe(duplex=False)
        self.parameters = parameters
        self.catchments = catchments
        self.catchments_type = catchments_type
        self.start_year = start_year
        self.end_year = end_year

    def run(self):
        if self.filename.endswith(".json"):
            models = []
            for catchment_code in self.catchments:
                models.extend(find(self.catchments_type, catchment_code, "models",
                                   start_year=self.start_year,
                                   end_year=self.end_year))
                self.child_connection.send(100 / len(self.catchments))
            with open(self.filename, "w", encoding="utf-8") as file:
                dump(models, file)
        else:
            rows = []
            header = []
            if self.catchments_type == "countries":
                header.append("Country code")
                header.append("Country name")
            elif self.catchments_type == "districts":
                header.append("District code")
                header.append("District name")
            elif self.catchments_type == "rivers":
                header.append("River code")
                header.append("River name")
            elif self.catchments_type == "waterbodies":
                header.append("Waterbody code")
                header.append("Waterbody name")
            else:
                header.append("Station code")
                header.append("Station name")
            header.append("Year")
            header.append("Parameter code")
            header.append("Parameter name")
            header.append("Source type")
            header.append("Area, km²")
            header.append("Natural discharge, kg")
            header.append("Anthropogenic discharge, kg")
            header.append("Atmospheric deposition, kg")
            header.append("Total discharge, kg")
            header.append("Retention, kg")
            rows.append(header)
            for catchment_code in self.catchments:
                for model in find(self.catchments_type, catchment_code, "models",
                                  start_year=self.start_year,
                                  end_year=self.end_year):
                    for parameter_code, parameter_name in self.parameters.items():
                        for source_code, source_name in SOURCES.items():
                            rows.append([
                                model["code"],
                                model["name"],
                                model["year"],
                                parameter_code,
                                parameter_name,
                                source_name,
                                sumattr(model, source_code, "area"),
                                sumattr(model, source_code,
                                        "naturalDischarge", parameter_code),
                                sumattr(model, source_code,
                                        "anthropogenicDischarge", parameter_code),
                                sumattr(model, source_code,
                                        "atmosphericDeposition", parameter_code),
                                sumattr(model, source_code,
                                        "totalDischarge", parameter_code),
                                sumattr(model, source_code, "retention", parameter_code)])

                self.child_connection.send(100 / len(self.catchments))

            with open(self.filename, "w", newline="") as file:
                writer(file, delimiter=";").writerows(rows)


class EstimateFrame(ModelFrame):

    def __init__(self, master, parameters=PARAMETERS):
        super().__init__(master, parameters)
        frame2 = self.nametowidget(self.book2.select())
        frame2.time_step_combobox.config(state="readonly")
        frame2.area_specific = BooleanVar()
        frame2.area_specific_checkbox = Checkbutton(frame2, text="Area specific",
                                                    variable=frame2.area_specific)
        frame2.area_specific_checkbox.grid(row=6, padx=4, pady=16, sticky=W)

    def save(self):
        filename = asksaveasfilename(defaultextension=".csv",
                                     filetypes=[("CSV File", ".csv")])
        if not filename:
            return
        frame1 = self.nametowidget(self.book1.select())
        frame2 = self.nametowidget(self.book2.select())
        parameters = frame2.view.selection()
        if not parameters:
            parameters = frame2.view.get_children()
        catchments = frame1.view.selection()
        if not catchments:
            catchments = frame1.view.get_children()
        LoadingWindow(self, EstimateProcess(filename, catchments,
                                            frame1.collection,
                                            parameters,
                                            frame2.start_year.get(),
                                            frame2.end_year.get(),
                                            frame2.time_step.get(),
                                            frame2.area_specific.get()))


class EstimateProcess(Process):

    def __init__(self, filename, catchments, catchments_type,
                 parameters, start_year, end_year, time_step="year",
                 area_specific=False):
        super().__init__(daemon=True)
        self.filename = filename
        self.parent_connection, self.child_connection = Pipe(duplex=False)
        self.parameters = parameters
        self.catchments = catchments
        self.catchments_type = catchments_type
        self.start_year = start_year
        self.end_year = end_year
        self.time_step = time_step
        self.area_specific = area_specific

    def run(self):
        rows = []
        header = []
        if self.catchments_type == "countries":
            header.append("Country code")
            header.append("Country name")
        elif self.catchments_type == "districts":
            header.append("District code")
            header.append("District name")
        elif self.catchments_type == "rivers":
            header.append("River code")
            header.append("River name")
        elif self.catchments_type == "waterbodies":
            header.append("Waterbody code")
            header.append("Waterbody name")
        else:
            header.append("Station code")
            header.append("Station name")
        header.append("Parameter code")
        header.append("Parameter name")
        header.append("Date")
        header.append("Value")
        header.append("Unit")
        rows.append(header)
        for catchment_code, catchment_name in self.catchments.items():
            for parameter_code, parameter_name in self.parameters.items():
                for estimate in find(self.catchments_type, catchment_code, "estimates",
                                     start_year=self.start_year,
                                     end_year=self.end_year,
                                     parameter=parameter_code.lower(),
                                     time_step=self.time_step.lower().replace(" ", "-"),
                                     area_specific=str(self.area_specific).lower()):
                    rows.append([
                        catchment_code,
                        catchment_name,
                        parameter_code,
                        parameter_name,
                        estimate["date"],
                        estimate["value"],
                        estimate["unit"]])

                self.child_connection.send(100 / len(self.catchments)
                                           / len(self.parameters))

        with open(self.filename, "w", newline="") as file:
            writer(file, delimiter=";").writerows(rows)


class ParameterFrame(Frame):

    def __init__(self, master, parameters=PARAMETERS):
        super().__init__(master)
        self.view = Tableview(self)
        self.view.grid(row=0, column=1, rowspan=9, sticky=N+S+E+W)
        self.rowconfigure(8, weight=1)
        self.columnconfigure(1, weight=1)
        self.view.scrollbar.grid(row=0, column=2, rowspan=9, sticky=N+S)
        years = [year for year in reversed(range(1900, date.today().year))]
        self.start_year = StringVar(self)
        self.start_year_label = Label(self, text="Start year")
        self.start_year_label.grid(row=0, padx=5, pady=(16, 2), sticky=W)
        self.start_year_combobox = Combobox(self, state="readonly", textvariable=self.start_year,
                                            values=years)
        self.start_year_combobox.current(0)
        self.start_year_combobox.bind(
            "<<ComboboxSelected>>", self.update_end_year)
        self.start_year_combobox.grid(row=1, padx=5, sticky=W+E)
        self.end_year = StringVar(self)
        self.end_year_label = Label(self, text="End year")
        self.end_year_label.grid(row=2, padx=5, pady=(16, 2), sticky=W)
        self.end_year_combobox = Combobox(self, state="readonly", textvariable=self.end_year,
                                          values=years)
        self.end_year_combobox.current(0)
        self.end_year_combobox.bind(
            "<<ComboboxSelected>>", self.update_start_year)
        self.end_year_combobox.grid(row=3, padx=5, sticky=W+E)
        for parameter_code, parameter_name in parameters.items():
            self.view.append(parameter_code, parameter_name)

    def update_start_year(self, *args):
        if self.start_year.get() > self.end_year.get():
            self.start_year.set(self.end_year.get())

    def update_end_year(self, *args):
        if self.end_year.get() < self.start_year.get():
            self.end_year.set(self.start_year.get())


class StationFrame(Frame):

    def __init__(self, master):
        super().__init__(master)
        self.collection = "stations"
        self.subcollection = "stations"
        self.view = Tableview(self)
        self.view.grid(row=0, column=1, rowspan=13, sticky=N+S+E+W)
        self.view.scrollbar.grid(row=0, column=2, rowspan=13, sticky=N+S)
        self.country_code = StringVar(self)
        self.country_code.trace_add("write", self.update)
        self.country_code_label = Label(self, text="Country code")
        self.country_code_label.grid(row=0, padx=5, pady=(15, 2), sticky=W)
        self.country_code_entry = Entry(
            self, textvariable=self.country_code, width=23)
        self.country_code_entry.grid(row=1, padx=5)
        self.district_code = StringVar(self)
        self.district_code.trace_add("write", self.update)
        self.district_code_label = Label(self, text="District code")
        self.district_code_label.grid(row=2, padx=5, pady=(15, 2), sticky=W)
        self.district_code_entry = Entry(
            self, textvariable=self.district_code, width=23)
        self.district_code_entry.grid(row=3, padx=5)
        self.river_code = StringVar(self)
        self.river_code.trace_add("write", self.update)
        self.river_code_label = Label(self, text="River code")
        self.river_code_label.grid(row=4, padx=5, pady=(15, 2), sticky=W)
        self.river_code_entry = Entry(
            self, textvariable=self.river_code, width=23)
        self.river_code_entry.grid(row=5, padx=5)
        self.code = StringVar(self)
        self.code.trace_add("write", self.update)
        self.code_label = Label(self, text="Station code")
        self.code_label.grid(row=6, padx=5, pady=(15, 2), sticky=W)
        self.code_entry = Entry(self, textvariable=self.code, width=23)
        self.code_entry.grid(row=7, padx=5)
        self.name = StringVar(self)
        self.name.trace_add("write", self.update)
        self.name_label = Label(self, text="Station name")
        self.name_label.grid(row=8, padx=5, pady=(15, 2), sticky=W)
        self.name_entry = Entry(self, textvariable=self.name, width=23)
        self.name_entry.grid(row=9, padx=5)
        self.type = StringVar(self)
        self.type_label = Label(self, text="Station type")
        self.type_label.grid(row=10, padx=5, pady=(15, 2), sticky=W)
        self.type_combobox = Combobox(self, state="readonly", textvariable=self.type,
                                      values=["", "Hydrochemical", "Hydrological"])
        self.type_combobox.current(1)
        self.type_combobox.bind("<<ComboboxSelected>>", self.update)
        self.type_combobox.grid(row=11, padx=5)
        self.rowconfigure(12, weight=1)
        self.columnconfigure(1, weight=1)
        self.bind("<Visibility>", self.update)

    def update(self, *args):
        self.view.delete(*self.view.get_children())
        params = {}
        if self.code.get():
            params["code"] = self.code.get()
        if self.name.get():
            params["name"] = self.name.get()
        if self.collection == "stations" and self.type.get():
            params["type"] = self.type.get().lower()
        stations = []
        if self.river_code.get():
            self.country_code_entry.config(state=DISABLED)
            self.district_code_entry.config(state=DISABLED)
            stations = find("rivers", self.river_code.get(),
                            self.subcollection, **params)
        elif self.district_code.get():
            self.country_code_entry.config(state=DISABLED)
            self.river_code_entry.config(state=DISABLED)
            stations = find("districts", self.district_code.get(),
                            self.subcollection, **params)
        elif self.country_code.get():
            self.district_code_entry.config(state=DISABLED)
            self.river_code_entry.config(state=DISABLED)
            stations = find("countries", self.country_code.get(),
                            self.subcollection, **params)
        else:
            self.country_code_entry.config(state=NORMAL)
            self.district_code_entry.config(state=NORMAL)
            self.river_code_entry.config(state=NORMAL)
            stations = find(self.collection, **params)
        for station in stations:
            self.view.append(station["code"], station["name"])


class WaterbodyFrame(StationFrame):

    def __init__(self, master):
        super().__init__(master)
        self.collection = "waterbodies"
        self.subcollection = "waterbodies"
        self.code_label.configure(text="Waterbody code")
        self.name_label.configure(text="Waterbody name")
        self.type_label.grid_forget()
        self.type_combobox.grid_forget()


class RiverFrame(StationFrame):

    def __init__(self, master):
        super().__init__(master)
        self.collection = "rivers"
        self.subcollection = "rivers" if self.district_code.get() else "tributaries"
        self.river_code_label.configure(text="Parent river code")
        self.code_label.configure(text="River code")
        self.name_label.configure(text="River name")
        self.type_label.grid_forget()
        self.type_combobox.grid_forget()


class DistrictFrame(StationFrame):

    def __init__(self, master):
        super().__init__(master)
        self.collection = "districts"
        self.subcollection = "subdistricts"
        self.district_code_label.configure(text="Parent district code")
        self.code_label.configure(text="District code")
        self.name_label.configure(text="District name")
        self.river_code_label.grid_forget()
        self.river_code_entry.grid_forget()
        self.type_label.grid_forget()
        self.type_combobox.grid_forget()


class CountryFrame(StationFrame):

    def __init__(self, master):
        super().__init__(master)
        self.collection = "countries"
        self.subcollection = None
        self.code_label.configure(text="Country code")
        self.name_label.configure(text="Country name")
        self.country_code_label.grid_forget()
        self.country_code_entry.grid_forget()
        self.district_code_label.grid_forget()
        self.district_code_entry.grid_forget()
        self.river_code_label.grid_forget()
        self.river_code_entry.grid_forget()
        self.type_label.grid_forget()
        self.type_combobox.grid_forget()


class Tableview(Treeview):

    def __init__(self, master):
        super().__init__(master, columns=["name"])
        self.column("#0", width=100, stretch=NO)
        self.heading("#0", text="Code")
        self.heading("#1", text="Name")
        self.bind("<Control-a>", self.select_all)
        self.bind("<Control-c>", self.copy)
        self.scrollbar = Scrollbar(master, command=self.yview)
        self.configure(yscrollcommand=self.scrollbar.set)

    def append(self, code, name):
        super().insert("", END, iid=code, text=code, values=[name])

    def copy(self, event=None):
        self.clipboard_clear()
        self.clipboard_append(self.item(self.focus())["text"])
        self.update()

    def get_children(self):
        return {code: self.set(code, "name") for code in super().get_children()}

    def select_all(self, event=None):
        self.selection_set(*self.get_children())

    def selection(self):
        return {code: self.set(code, "name") for code in super().selection()}


if __name__ == "__main__":
    freeze_support()
    EstModelClient().mainloop()
