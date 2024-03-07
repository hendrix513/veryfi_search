# veryfi_search
lightweight app for processing documents with Veryfi and searching for results

# requirements
Docker must be installed and running on local machine

# deployment instructions
- clone repo
- cd into cloned directory
- modify JWT_SECRET_KEY value in .env file to a value of your choice
- run command 'docker compose up'

Watch logs in terminal, after several seconds you should see log output from the Flask server like such- this indicates app is ready:
app-1            |  * Running on all addresses (0.0.0.0)
app-1            |  * Running on http://127.0.0.1:5000
app-1            |  * Running on http://172.21.0.3:5000

By default, Flask app listens on port 5000 though this can be changed in docker-compose.yml if desired

# using the app
assume APP_URL = 'localhost' and PORT equals chosen port for Flask app (see above)

to register as a user:
POST {APP_URL}/register 
BODY:
   client_id: required- client id for Veryfi api
   client_secret: required- client secret for Veryfi api
   username: required- username for Veryfi api,
   api_key: required - api key for Veryfi api,
   password: required - password for logging into this app
PYTHON EXAMPLE:
   ```
   d = dict(client_id='my client id',
           client_secret='client secret',
           username='my username',
           api_key='my api key',
           password="my password")

   resp = requests.post('http://localhost:5000/register', json=d)
   ```

to login:
POST {APP_URL}/login 
BODY:
   username: required- username for Veryfi api,
   password: required - password for logging into this app
HEADERS:
  'Content-Type': 'application/json' - required
PYTHON EXAMPLE:
   ```
   d = dict(username='my_username',
           password="my_password")
   resp = requests.post('http://localhost:5000/login', json=d, headers={'Content-Type': 'application/json'})
   ```

Upon success, /login will return 200 status code with body like {'access_token': ACCESS_TOKEN}

to upload document:
POST {APP_URL}/doc
FILES:
 required - file path of document to be processed
HEADERS:
 required- "Authorization": f"Bearer {ACCESS_TOKEN (see above)}"
PYTHON EXAMPLE:
  ```
  upload_url = 'http://localhost:5000/doc'
  file_path = '/Users/michaelschwartz/Downloads/MICHAEL SCHWARTZ - Sale Invoice.pdf'  # Replace this with the actual file path

  with open(file_path, 'rb') as file:
    files = {'file': file}
    response = requests.post(upload_url, files=files, headers={"Authorization": f"Bearer {access_token}"})

  ```

Upon success, endpoint will return 200 status code with body like:
 {'message': 'Document uploaded successfully'
  'doc': uploaded document processed by Veryfi}

to search documents:
GET {APP_URL}/search
params:
 query: required - json dump of Elastic query to run against processed documents
  (note- this query body is sent as payload to ElasticSearch's '/_search' endpoint see https://www.elastic.co/guide/en/elasticsearch/reference/current/search-search.html for more information on forming queries)
HEADERS:
 required- "Authorization": f"Bearer {ACCESS_TOKEN (see above)}"
PYTHON EXAMPLE:
  ```
  query = json.dumps({
  "query": {
    "match": {
      "vendor.name": {
        "query": "Trek Bicycle Providence"
      }
    }
  }
})
  url =  'http://localhost:5000/search'

  response = requests.get(url, params={"query": query}, headers={"Authorization": f"Bearer ACCESS_TOKEN (see above)"})

  ```
Upon success, endpoint will return 200 status code with body like:
 {'results': [processed documents matching the input query that were uploaded by current user]}

# design notes
This is a dockerized application that connects Flask instance with an ElasticSearch cluster. It is meant to allow a user process documents like receipts through the Veryfi API, and then search over the documents they have processed

# tradeoffs
- There are no unit tests for this app- with more time I would have like to add these
- '/doc' endpoint returns parsed document upon success. This might be a bad idea in a production environment with network constraints. It might be useful for the caller to use, but depending on context could also be removed
- '/search' endpoint only takes a 'query' parameter to pass to Elastic- in a production scenario I could see extending this logic to also accept more arguments
- authentication information is stored and accessed in memory in the app- in a production scenario this of course would be moved to a database service or something similar
- with more time I would have liked to add a caching layer to store recent search results
- with more time I would have liked to add remote fileserver like s3 as a dependency, to store uploaded files
