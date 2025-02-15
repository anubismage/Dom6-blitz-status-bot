import requests
from bs4 import BeautifulSoup

# Example usage
# game_id = '520'
# html_content = get_raw_html_page(game_id)

def extract_status_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    status_div = soup.find('div', id='status')
    lobby_name = soup.find('h1').text.strip()
    if status_div:
        pane_status_div = status_div.find('div', class_='pane status')
        players = []

        # Find the players div and get all striped tables
        players_div = soup.find('div', class_='players')
        if players_div:
            player_tables = players_div.find_all("table", class_="striped-table")
            for player_table in player_tables:
                for row in player_table.find_all("tr", class_=lambda x: x and "disciple" in x):
                    nation_td = row.find("td", class_="nation-name wide-column")
                    status_td = row.find_all("td")[-1]  # Last <td>
                    
                    if nation_td and status_td:
                        nation_name = ""
                        nation_b = nation_td.find("b")
                        nation_epithet = nation_td.find("span", class_="epithet")
                        if nation_b:
                            nation_name += nation_b.text.strip()
                        if nation_epithet:
                            nation_name += nation_epithet.text.strip()
                        
                        status = status_td.text.strip()
                        players.append({"nation_name": nation_name, "status": status})

        game_info = {}
        if pane_status_div:
            rows = pane_status_div.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) == 2:
                    key = cols[0].text.strip().lower().replace(" ", "_")
                    value = cols[1].text.strip()
                    game_info[key] = value

        return lobby_name, players, game_info
    else:
        return lobby_name, 'No status div found', 'No status div found'

