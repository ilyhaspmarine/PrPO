import configparser as cp
import copy
from datetime import datetime
import random

class RatingSystem:
    def __init__(self, infr_module):
        self.__infr_module = infr_module
        self.__preset_steps = [1/9, 1/7, 1/5, 1/3, 1, 3, 5, 7, 9]
        self.initialize_system()

    def __build_apartment_square_scale(self, number = 1):
        scale_max = self.__get_max_of_scale(self.__scales['квартира']['площадь'])
        if number < 2:
            square_norm = 33
        elif number == 2:
            square_norm = 42
        else:
            square_norm = number*18
        scale_high = 1.3*square_norm
        scale_step = scale_high / scale_max
        self.__scales['квартира']['площадь']['scale'] = {}
        for i in range(0, scale_max):
            self.__scales['квартира']['площадь']['scale'][i] = [0 + i*scale_step, 0 + (i + 1)*scale_step]
        self.__scales['квартира']['площадь']['scale'][scale_max] = [scale_high, float('inf')]

    def __read_scales(self):
        self.__scales = {}
        cp1 = cp.ConfigParser()
        cp2 = cp.ConfigParser()
        cp1.read('./config/criterions.ini', encoding='utf-8')
        cp2.read('./config/scales.ini', encoding='utf-8')
        for est_type in cp1.sections():
            self.__scales[est_type] = {}
            for criterion in cp1[est_type]:
                cp2_dict = dict(cp2[cp1[est_type][criterion]])
                self.__scales[est_type][cp1[est_type][criterion]] = {}
                self.__scales[est_type][cp1[est_type][criterion]]['fieldname'] = cp2_dict['fieldname']
                self.__scales[est_type][cp1[est_type][criterion]]['scale_type'] = cp2_dict['type']
                self.__scales[est_type][cp1[est_type][criterion]]['scale'] = {}
                if self.__scales[est_type][cp1[est_type][criterion]]['scale_type'] == '1':
                    scale_low = float(cp2[cp1[est_type][criterion]]['low'])
                    scale_high = float(cp2[cp1[est_type][criterion]]['high'])
                    scale_max = int(cp2[cp1[est_type][criterion]]['max'])
                    scale_min = int(cp2[cp1[est_type][criterion]]['min'])
                    scale_step = (scale_high - scale_low) / (scale_max - scale_min)
                    for i in range(scale_min, scale_max):
                        self.__scales[est_type][cp1[est_type][criterion]]['scale'][i] = [
                            scale_low + (i - scale_min) * scale_step, scale_low + (i - scale_min + 1) * scale_step]
                    self.__scales[est_type][cp1[est_type][criterion]]['scale'][scale_max] = [scale_high, float('inf')]
                elif self.__scales[est_type][cp1[est_type][criterion]]['scale_type'] == '2':
                    scale_low = float(cp2[cp1[est_type][criterion]]['low'])
                    scale_high = float(cp2[cp1[est_type][criterion]]['high'])
                    scale_max = int(cp2[cp1[est_type][criterion]]['max'])
                    scale_step = (scale_high - scale_low) / scale_max
                    self.__scales[est_type][cp1[est_type][criterion]]['scale'][0] = [float('inf'), scale_high]
                    for i in range(1, scale_max + 1):
                        self.__scales[est_type][cp1[est_type][criterion]]['scale'][i] = [
                            scale_high - (i - 1) * scale_step, scale_high - i * scale_step]
                elif self.__scales[est_type][cp1[est_type][criterion]]['scale_type'] == '3':
                    for value in list(cp2_dict.keys())[2:]:
                        self.__scales[est_type][cp1[est_type][criterion]]['scale'][value] = int(cp2_dict[value])
        self.__build_apartment_square_scale()

    def __read_penalties(self):
        cp1 = cp.ConfigParser()
        cp1.read('./config/penalties.ini', encoding='utf-8')
        for penalty in cp1.sections():
            self.__penalties[penalty] = {}
            for value in cp1[penalty].keys():
                self.__penalties[penalty][value] = float(cp1[penalty][value])

    def __read_preset(self):
        cp1 = cp.ConfigParser()
        cp1.read('./config/preset_apart.ini', encoding='utf-8')
        self.__preset['квартира'] = {}
        for criterion in cp1.sections():
            self.__preset['квартира'][criterion] = {}
            for key in cp1[criterion]:
                self.__preset['квартира'][criterion][key] = eval(cp1[criterion][key])

    def __read_filters(self):
        cp1 = cp.ConfigParser()
        cp1.read('./config/filters.ini', encoding='utf-8')
        for est_type in cp1.sections():
            self.__filters[est_type] = {}
            for filter in cp1[est_type]:
                self.__filters[est_type][filter] = cp1[est_type][filter]

    def __build_work_preset(self, est_type):
        preset_work = copy.deepcopy(self.__preset[est_type])
        return preset_work

    def __modify_preset_row(self, preset_work, row_key, steps):
        for col_key in preset_work[row_key].keys():
            index = self.__preset_steps.index(preset_work[row_key][col_key]) + steps
            if index > 8:
                index = 8
            preset_work[row_key][col_key] = self.__preset_steps[index]
            preset_work[col_key][row_key] = 1 / preset_work[row_key][col_key]

    def __reset_preset_row(self, preset_work, row_key, filters):
        preset_work[row_key] = copy.deepcopy(self.__preset[filters['est_type']][row_key])

    def __calc_coefficients_from_preset(self, preset_work):
        coefs = {}
        crit_cntr = len(preset_work.keys())
        sum = 0
        for row_key in preset_work.keys():
            coefs[row_key] = 1
            for col_key in preset_work[row_key].keys():
                coefs[row_key] *= preset_work[row_key][col_key]
            coefs[row_key] = coefs[row_key] ** (1 / crit_cntr)
            sum += coefs[row_key]
        for row_key in preset_work.keys():
            coefs[row_key] /= sum
        return coefs

    def __define_coefficients(self, filters):
        preset_work = self.__build_work_preset(filters['est_type'])
        if filters['est_type'] == 'квартира':
            self.__build_apartment_square_scale(filters['fam_number'])
        steps = 2
        filt_dict = self.__filters[filters['est_type']]
        for filter in list(filters.keys())[2:]:
            self.__modify_preset_row(preset_work, self.__filters[filters['est_type']][filter], steps)
        return self.__calc_coefficients_from_preset(preset_work)

    def __eval_item_by_scale(self, item, scale):
        fieldname = scale['fieldname']
        if item.get(fieldname) is None:
            return 0
        if scale['scale_type'] == '3':
            try:
                value = scale['scale'][item[fieldname]]
            except KeyError:
                value = 0
            return value
        elif scale['scale_type'] == '1':
            for value in scale['scale'].keys():
                if scale['scale'][value][0] <= item[fieldname] < scale['scale'][value][1]:
                    return value
        elif scale['scale_type'] == '2':
            for value in scale['scale'].keys():
                if scale['scale'][value][0] >= item[fieldname] > scale['scale'][value][1]:
                    return value

    def __get_max_of_scale(self, scale):
        if scale['scale_type'] == '3':
            return max(scale['scale'].values())
        elif scale['scale_type'] == '1' or scale['scale_type'] == '2':
            return max(scale['scale'].keys())

    def initialize_system(self):
        self.__scales = {}
        self.__penalties = {}
        self.__preset = {}
        self.__filters = {}
        # шкалы
        self.__read_scales()
        # штрафные коэф.
        self.__read_penalties()
        # пресет
        self.__read_preset()
        # фильтры
        self.__read_filters()

    def __penult_collection(self, collection, rating):
        for item in collection:
            item_id = item['id']
            for penalty in self.__penalties:
                try:
                    rating[item_id] *= self.__penalties[penalty][str(item[penalty])]
                except KeyError:
                    if penalty == 'floor':
                        if item['floor'] == item['floor_max']:
                            rating[item_id] *= self.__penalties[penalty]['max']

    def __get_ages(self, collection):
        for item in collection:
            if item.get('build_year') is not None:
                item['age'] = datetime.now().year - item['build_year']

    def __get_infrastructure(self, collection):
        self.__infr_module.get_infrastructure(collection)

    def rate_collection(self, filters, collection):
        self.__get_ages(collection)
        # self.__get_infrastructure(collection)
        coefs = self.__define_coefficients(filters)
        print(coefs)
        rating = {}
        max = 0
        for criterion in self.__scales[filters['est_type']].keys():
            max += coefs[criterion] * self.__get_max_of_scale(self.__scales[filters['est_type']][criterion])
        for item in collection:
            item_id = item['id']
            #print(item_id)
            rating[item_id] = 0
            for criterion in self.__scales[filters['est_type']].keys():
                tmp = coefs[criterion] * self.__eval_item_by_scale(item, self.__scales[filters['est_type']][criterion])
                #print(criterion, tmp)
                rating[item_id] += tmp
            rating[item_id] /= max
        self.__penult_collection(collection, rating)
        return rating

class PlaceHolder:

    def __init__(self):
        pass

    def get_infrastructure(self, collection):
        for item in collection:
            # item['schools'] = random.randint(0, 5)
            # item['stores'] = random.randint(0, 5)
            # item['stops'] = random.randint(0, 5)
            # item['pharmacies'] = random.randint(0, 5)
            # item['infants'] = random.randint(0, 5)
            # item['malls'] = random.randint(0, 5)
            # item['parks'] = random.randint(0, 5)
            # item['cl.store'] = random.randint(10, 2001)
            # item['cl.school'] = random.randint(10, 2001)
            # item['cl.infant'] = random.randint(10, 2001)
            # item['cl.polyclinic'] = random.randint(10, 2001)
            # item['cl.stop'] = random.randint(10, 1001)
            # item['cl.pharmacy'] = random.randint(10, 1001)

            item['schools'] = 1
            item['stores'] = 1
            item['stops'] = 1
            item['pharmacies'] = 1
            item['infants'] = 1
            item['malls'] = 1
            item['parks'] = 1
            item['cl.store'] = 500
            item['cl.school'] = 500
            item['cl.infant'] = 500
            item['cl.polyclinic'] = 500
            item['cl.stop'] = 500
            item['cl.pharmacy'] = 500

rs = RatingSystem(PlaceHolder())

collection = [
    {
        'id': '1',
        'rooms': 1,
        'house_type': 'кирпичный',
        'conditioner': 'кондиционер',
        'repair': None,
        'elevators': 1,
        'balcony': None,
        'parking': 'наземная',
        'square': 34,
        'floor': 1,
        'floor_max': 5,
        'toilet': 'совмещенный',
        'build_year': 1964,
        'pharmacies': 0,
        'cl.pharmacy': 1300,
        'schools': 2,
        'cl.school': 900,
        'infants': 7,
        'cl.infant': 71,
        'stores': 8,
        'cl.store': 1300,
        'stops': 5,
        'cl.stop': 350,
        'cl.polyclinic': 1000,
        'parks': 8,
        'malls': 6
    },
    {
        'id': '2',
        'rooms': 2,
        'repair': 'косметический',
        'elevators': 1,
        'balcony': None,
        'house_type': 'кирпичный',
        'conditioner': 'кондиционер',
        'parking': 'наземная',
        'square': 68,
        'floor': 3,
        'floor_max': 6,
        'toilet': 'раздельный',
        'build_year': 1952,
        'pharmacies': 19,
        'cl.pharmacy': 170,
        'schools': 3,
        'cl.school': 650,
        'infants': 14,
        'cl.infant': 71,
        'stores': 10,
        'cl.store': 500,
        'stops': 14,
        'cl.stop': 200,
        'cl.polyclinic': 650,
        'parks': 8,
        'malls': 6
    },
    {
        'id': '3',
        'rooms': 3,
        'repair': None,
        'elevators': 1,
        'balcony': 'балкон',
        'house_type': 'кирпичный',
        'conditioner': None,
        'parking': None,
        'square': 57,
        'floor': 5,
        'floor_max': 5,
        'toilet': 'совмещенный',
        'build_year': 1961,
        'pharmacies': 5,
        'cl.pharmacy': 150,
        'schools': 4,
        'cl.school': 300,
        'infants': 8,
        'cl.infant': 400,
        'stores': 7,
        'cl.store': 600,
        'stops': 7,
        'cl.stop': 550,
        'cl.polyclinic': 1900,
        'parks': 2,
        'malls': 1
    },
    {
        'id': '4',
        'rooms': 2,
        'repair': 'косметический',
        'elevators': 1,
        'balcony': 'лоджия',
        'house_type': 'кирпичный',
        'conditioner': None,
        'parking': None,
        'square': 66,
        'floor': 7,
        'floor_max': 9,
        'toilet': 'раздельный',
        'build_year': 2009,
        'pharmacies': 8,
        'cl.pharmacy': 550,
        'schools': 12,
        'cl.school': 450,
        'infants': 16,
        'cl.infant': 10,
        'stores': 11,
        'cl.store': 400,
        'stops': 9,
        'cl.stop': 260,
        'cl.polyclinic': 600,
        'parks': 0,
        'malls': 0
    },
    {
        'id': '5',
        'rooms': 3,
        'repair': None,
        'elevators': 1,
        'balcony': 'лоджия',
        'house_type': 'панельный',
        'conditioner': None,
        'parking': None,
        'square': 79.6,
        'floor': 2,
        'floor_max': 9,
        'toilet': 'раздельный',
        'build_year': 1963,
        'pharmacies': 8,
        'cl.pharmacy': 270,
        'schools': 12,
        'cl.school': 450,
        'infants': 14,
        'cl.infant': 350,
        'stores': 12,
        'cl.store': 130,
        'stops': 8,
        'cl.stop': 500,
        'cl.polyclinic': 1000,
        'parks': 2,
        'malls': 1
    },
    {
        'id': '6',
        'rooms': 3,
        'repair': 'евроремонт',
        'elevators': 2,
        'balcony': 'лоджия',
        'house_type': 'панельный',
        'conditioner': None,
        'parking': None,
        'square': 68,
        'floor': 6,
        'floor_max': 12,
        'toilet': 'раздельный',
        'build_year': 1983,
        'pharmacies': 5,
        'cl.pharmacy': 160,
        'schools': 14,
        'cl.school': 270,
        'infants': 14,
        'cl.infant': 350,
        'stores': 12,
        'cl.store': 130,
        'stops': 8,
        'cl.stop': 500,
        'cl.polyclinic': 1000,
        'parks': 2,
        'malls': 1
    },
]

filters = {
    'est_type': 'квартира',
    'fam_number': 1
}



print(rs.rate_collection(filters, collection))
