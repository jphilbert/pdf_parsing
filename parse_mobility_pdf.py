###############################################################################
# Parses PDF and plots from https://www.google.com/covid19/mobility/
# Shout out to @Amarang on Github who had much of the insight
#
# Currently these methods will skipp the first two pages of the report which
# contain the overall data on the country / state. To get states use the US
# report, however this still poses a problem for overall countries.
###############################################################################

import datetime
from functools import reduce
from collections import defaultdict
import fitz                     # pip3 install --user PyMuPDF
from xml.dom import minidom


# 0 - county
# 1 - category
# 2 - baseline
# ... x 6 (=12)
# 13 - county - second
# ... x6 (=12)
# 26 - footer (optional)
# 27 - footer (optional)
# 28 - x-axis
# 29-33 - y-axis
# ... x 12 (=72)
# + '*'s (optional)


def parse_page_text(page):
    categories = (
        "Retail & recreation",
        "Grocery & pharmacy",
        "Parks",
        "Transit stations",
        "Workplace",
        "Residential")

    day_abbr = ('Mon ', 'Tue ', 'Wed ', 'Thu ', 'Fri ', 'Sat ', 'Sun ')
    exclude_list = ('+', '-', 'baseline', '*', 'need', 'not',
                    'we\x92ll', 'compared')

    data = []
    region = None
    lines = [i[4] for i in page.getText('blocks')]
    
    ########################################
    # Collect Text Data 
    ########################################
    for l in lines:
        l = l.strip()
        if not (l.lower().startswith(exclude_list) or
                l.startswith(day_abbr)):
            if l.startswith(categories):
                data.append([region, l.title()])
            else:
                region = l.replace(' County', '')

    if len(data) == 0:
        return {'date_range': [],
                'data': []}
    
    ########################################
    # Find X-axis and Parse 
    ########################################
    for l in lines:
        if l.startswith(day_abbr):
            tickdates = l
            break
    tickdates = tickdates.split()

    start_date = datetime.datetime.strptime(
        ' '.join(tickdates[1:3]) + ', 2020', '%b %d, %Y')

    end_date = datetime.datetime.strptime(
        ' '.join(tickdates[-2:]) + ', 2020', '%b %d, %Y')

    
    return {'date_range': [start_date, end_date],
            'data': data}
    

def parse_page_plots(page, date_range):
    svg = page.getSVGimage()
    svg = minidom.parseString(svg)
    svg = svg.childNodes[1].childNodes[1].childNodes[1].childNodes
    
    date_min = min(date_range)
    date_max = max(date_range)

    x_range = [70.29508, 418.96174]
    y_range = [133.16902, 597.8663]
    def coord_transform(v, rng):
        v = float(v)
        v = (v - rng[0]) / (rng[1]-rng[0])
        return v
        
    y_offset = 50
    
    paths = dict()
    
    for i in svg:
        if (i.nodeType == 1 and
            i.tagName == 'g' and
            len(i.childNodes) == 3):
            this_path = i.childNodes[1].childNodes[3].childNodes[1]

            # Position of Plot
            pos = this_path.getAttribute('transform')
            pos = pos.split(',')[-2:]
            x = coord_transform(pos[0], x_range)
            y = coord_transform(pos[1].strip(')'), y_range)
            
            pos = round(x*2 + y*3*3)
            
            # Path Data
            path = this_path.getAttribute('d')
            path = [float(i) for i in path.split() if not i.isalpha()]

            data = defaultdict(list)

            for x, y in zip(path[::2], path[1::2]):
                x = (date_min + x * (date_max - date_min)/200 +
                     datetime.timedelta(hours = 12)).date()
                # Remember SVG coords are upside-down
                y = (y_offset - y) * 100 / 60.0
                data[x].append(y)

            x = data.keys()
            x = sorted(x)
    
            y = [reduce(lambda a, b: a if abs(a) > abs(b) else b, data[i])
                 for i in x]

            paths[pos] = list(zip(x, y))

    return paths


def parse_page(page, verbose = False):
    text = parse_page_text(page)
    if verbose:
        print('Found {:,} text categories'.format(len(text['data'])))

    if len(text['data']) not in [6, 12]:
        if verbose:
            print('\tSkipping')
        return []

    plot = parse_page_plots(page, text['date_range'])
    if verbose:
        print('Found {:,} plots'.format(len(plot)))

    ########################################
    # Merge the Two 
    ########################################
    data = []

    for i, d_array in plot.items():
        data += [text['data'][i] + list(d) for d in d_array]

    return data
        

def parse_doc(doc, verbose = False):
    data = []
    i = 1
    for p in doc.pages():
        if verbose:
            print('Processing page {:,}'.format(i))
        i += 1
        data += parse_page(p, verbose)
    return data

