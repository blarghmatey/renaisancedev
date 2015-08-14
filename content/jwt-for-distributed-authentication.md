Title: Distributed Authentication With JSON Web Tokens
Date: 2015-08-13
Category: Development
Tags: Microservices, SOA
url: jwt-distributed-auth.html
save_as: jwt-distributed-auth.html

One of the hardest problems to tackle when dealing with service oriented architecture is managing authentication and authorization across the various systems. This is particularly troublesome when the initial application architecture is a monolith, as integrating an OAuth provider at a late stage of development can be a significant effort. I was recently faced with such a situation, necessitating a period of research and experimentation to come up with a solution that was simple to implement and reason about.

## Possible Solutions
In the course of my search for a centralized authorization framework I investigated the plausibility of various technologies including OAuth (version 1 _and_ version 2), OpenID and (briefly) SAML. The problem with each of these standards is that they introduce a significant amount of complexity to your application. In addition, in order to take full advantage of their strengths an overhaul of the existing authorization mechanism would be necessary.

## Enter JWT
After coming across the [JSON Web Token specification](https://tools.ietf.org/html/rfc7519) I realized that it was exactly what I had been looking for. By handling creation and verification of the token using a shared secret on the backend it becomes possible to send arbitrary `key=value` pairs between services to pass authorization information while the token signature acts as an implicit authentication.

JWTs can either be cryptographically signed using a one-way hashing algorithm (HS256 by default) or symmetrically encrypted with an X509 key. Both of these techniques are part of the larger [JOSE](https://datatracker.ietf.org/wg/jose/documents/) (Javascript Object Signing and Encryption) standard. The difference between these two approaches is that using a signature means the contents of the token can be decoded and used by the client side of your application, whereas encrypting the token renders the contents opaque to any system that doesn't possess the decryption key.

## How To Do It
Because a JWT is, fundamentally, just a JSON object it is easy to create an API endpoint for obtaining new tokens and include it in an existing application. I used the PyJWT library to make creation and verification of tokens simple and straightforward.

```python
import jwt
from flask import Flask
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/api/jwt', methods=['GET'])
def get_jwt():
    token = jwt.encode({'username': 'Renaissance Dev',
                        'role': 'super_admin',
                        'exp': datetime.utcnow() + timedelta(minutes=app.config.get('HAPYAK_JWT_LIFETIME', 60)),
                        'iat': datetime.utcnow(),
                       app.config.get('JWT_KEY', 'changeme'))
    response = make_response(token)
    response.set_cookie('jwt', token, domain='.renaissancedev.com')
    return response
```
This will generate a new token with an expiration period of 1 hour that contains the name of the authenticated user as well as their permission level. You can feel free to include any arbitrary data that you deem necessary for your application, making this a lightweight, out of band message transport. For my particular use case I included information such as a list of groups that the authenticated user has access to, removing the need for a separate API call to obtain that information. The generated token is then set as a cookie as well as returned in the body of the message, allowing it to be usable by browser clients as well as for programmatic access.

In my new service I can now use this token to verify that the person or application that is making a request is allowed to do so. Because there is no request/response cycle needed to obtain user credentials for login I am managing everything in a pre-request hook.

```python
from flask import Flask, request, make_response, g
import jwt

app = Flask(__name__)

@app.before_request
def process_token():
    token = request.cookies.get(
        'jwt',
        request.headers.get(
            'Authorization',
            jwt.encode({'exp': 0}, config.TOKEN_KEY)
        ))
    try:
        user_info = jwt.decode(token, app.config.TOKEN_KEY)
        g.user_info = user_info
    except jwt.ExpiredSignatureError as e:
        response = make_response('Your JWT has expired')
        response.status_code = 401
        return response
    except jwt.DecodeError as e:
        response = make_response('Your JWT is invalid')
        response.status_code = 401
        return response
```
This will check for a token in the 'jwt' cookie, falling back to retrieving one from the Authorization header. If there is no token present in either location a new, invalid token is created and stored in the token variable. Expired and invalid tokens will cause a 401 response, necessitating retrieval of a new token from the central authentication service. If the token is valid then the contents of the message body are stored in the flask thread-local object (`g`) for use in processing the request.

## Take-Aways
By using JWTs as a lightweight messaging and authentication mechanism in your microservice or service-oriented application architecture you can sidestep the need for more heavyweight technologies such as OAuth. In my particular case OAuth was unnecessary because the authorization information is all being used by applications that are under my control. If anything I said is unclear or incorrect please let me know in the comments.
