Title: Networking With Android
Date: 2015-04-02
Category: Development
Tags: android, networking, reactive programming

I wrote my first native Android application about 1 year ago. As part of that endeavor I had to learn a lot about the best way of doing things in Android. In particular, handling network requests required a fair amount of research, combined with a lot of trial and error.

The application that I was working on relied entirely on an HTTP API for handling state and data, so handling network requests properly was of paramount importance. I ended up using the fantastic [Retrofit](http://square.github.io/retrofit/) library from the excellent people at Square, which supports three different approaches to handling the data returned from each request. I ended up trying out all three of them over the course of building the application. At some points in the cycle of developing the app I actually had all three approaches in use at different locations, which caused a rather insidious bug that I will detail later.

#AsyncTask

The first method that I tried was to use the Android native [AsyncTask](http://developer.android.com/reference/android/os/AsyncTask.html) which requires a lot of boilerplate to make it work. The benefit of this approach is that there are a large number of resources available online to explain how to use an `AsyncTask` in your application.

In Retrofit, you can specify a return type in the method signature of a given endpoint which will make the method call synchronous. This means that if you attempt to call the endpoint on your main thread you will get a `NetworkOnMainThreadException` unless you explicitly set your application to allow this behavior (don't do it!). In order to make use of these synchronous calls it is necessary to wrap the execution in an `AsyncTask`. This ends up looking like:
```java
//Interface definition of method
@GET("/resources")
List<Resource> getResources();

//AsyncTask calling specified endpoint
private class GetResources extends AsyncTask<Object, Void, List<Resource>> {

    @Override
    protected List<Resource> doInBackground(Object... params) {
        List<Resource> resourceList = retrofitService.getResources();
        return resourceList;
    }

    @Override
    protected void onPostExecute(List<Resource> result) {
        //Do something interesting with the resourceList here
        ...
    }
}

//Calling the AsyncTask
new GetResources().execute();
```
This specifies an endpoint that will return a list of Resource objects and it will execute in a blocking manner. Inside of the `doInBackground` method of the `AsyncTask` we call the method and return the resulting list. The `onPostExecute` method then receives the return value of the `doInBackground` method and processes it in whatever manner is desired.

The benefit of using an `AsyncTask` is that it is easy to reason about the order of operations for a given endpoint interaction. However, the code base quickly becomes cluttered with anonymous inner classes everywhere that you need to make a network request.

#Callbacks

After realizing the pain points of handling `AsyncTasks` I finally understood why the `Callback` approach of Retrofit was so beneficial. Rather than having to litter your code with anonymous classes that extend `AsyncTask` you can now write a method that returns a callback object. Inside of the callback object, there are two methods to implement for handling success and failure cases. Rewriting our `AsyncTask` example looks like this:
```java
//Interface definition of method
@GET("/resources")
void getResources(Callback<List<Resource>> resourceCallback);

//Callback for handling network response
private Callback<List<Resource>> resourceCallback(){
    return new Callback<List<Resource>>() {

        @Override
        public void success(List<Resource> resourceList, Response response) {
            //Do something successful!
        }

        @Override
        public void failure(RetrofitError error) {
            //Handle failure case
        }
    };
}

//Using the callback
retrofitClient.getResources(resourceCallback());
```
If you prefer, it is also possible to inline the definition of the callback with the method call. With Java 8 lambdas, it gets even more concise. One of the big benefits to using callbacks instead of synchronous returns is that you can just write the logic for handling failure cases without having to do the failure determination on your own.

#RxAndroid
While the callback approach requires less boilerplate than `AsyncTask`, it is still somewhat verbose. Using RxAndroid with Retrofit makes the code more natural to read and understand, as well as providing a number of convenient APIs to more finely control the processing of response data. Another big benefit to using RxAndroid is that you can chain API calls together for cases where you only care about the response from one request as an input to the next one.

Rewriting our example again, it now looks like this:
```java
//Interface definition of method
@GET("/resources")
Observable<List<Resource>> getResources();

//Calling the endpoint
retrofitClient.getResources().onError(
    //Handle failure
).subscribe(
    //Do something interesting
);
```
There are also a number of other useful things that you can do when calling the endpoint, such as retries or (as mentioned above) mapping together two network requests.
```java
//Calling the endpoint with retries
retrofitClient.getResources().retry(5).subscribe();

//Combining network requests

//New endpoint definition
@GET("/resources/{resource_id}")
Observable<ResourceInfo> getResourceDetails(@Path("resource_id") String resource_id);

//Chaining together both endpoints
retrofitClient.getResources().flatMap(
    resource -> retrofitClient.getResourceDetails(resource)
).subscribe(
    //Do something with resource details here
)
```
I won't attempt to show even a fraction of what you can do with the RxJava API because there are just too many possibilities. I recommend reading the [documentation](http://reactivex.io/) for more information about the myriad ways that reactive programming with observables can transform how you think about your program. I also recommend reading [these](http://futurice.com/blog/top-7-tips-for-rxjava-on-android) [posts](http://blog.danlew.net/2014/09/15/grokking-rxjava-part-1/) to give you a better understanding of how to take advantage of this fantastic library.'''verify

One thing that bit me while working on this application is that if your `subscribe` function does any manipulation of the UI, you have to prefix it with `observeOn(AndroidSchedulers.mainThread())`. If you forget to do this, you will be scratching your head and pounding your desk, wondering why nothing is happening (I know because it happened to me several times).

#The Bug
The API that I was connecting to for this application used OAuth for authentication of all requests. In order to handle expired tokens, I added this code as a `RequestInterceptor`:
```java
private RequestInterceptor bearerHeader = new RequestInterceptor() {
    @Override
    public void intercept(RequestFacade request) {
        if(new Date().after(ApiUser.authTokens.expireTime)){
            fetchingToken = 1;
            try {
                retrofitAuthServiceClient.authToken("client_credentials", //Use the client_credentials authentication method
                    ApiUser.getAuthKeys(), //Get the keys used for authenticating with the OAuth endpoint
                    new Callback<ApiTokens>() {
                            @Override
                            public void success(ApiTokens apiTokens, Response response) {
                                ApiUser.authTokens.updateTokens(apiTokens); //Update the cached token with the new one
                                fetchingToken = 0;
                            }

                            @Override
                            public void failure(RetrofitError error) {
                                fetchingToken = 0;
                            }
                        }
                );
            } catch (UnsupportedEncodingException e) {
                e.printStackTrace();
            }
        }
        while (fetchingToken > 0){
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
        request.addHeader("Authorization", user.getBearerToken()); //Add the cached token to the authorization header
    }
};
```
This worked great until I started refactoring the application to use observables. At one point during development, I had instances of all three approaches in use at different locations. In the end I changed everything to use RxAndroid, but before I got to that point I started having issues with certain API requests failing due to an invalid authentication token. Before introducing observables into the codebase I hadn't seen this bug, so I was baffled by why it started happening all of a sudden. After much frustration and confusion I finally realized that it was because of the fact that the failing request implemented an observable interface, whereas the token refresh used callbacks. The subscription on the observable was trying to process the response before the token had been retrieved. Classic race condition. In order to squash this particular bug I rewrote the request interceptor to use observables, like the rest of the application. What I ended up with looked like this:
```java
private RequestInterceptor bearerHeader = new RequestInterceptor() {
    @Override
    public void intercept(RequestFacade request) {
        if (new Date().after(ApiUser.authTokens.expireTime)) {
            fetchingToken = 1;
            try {
                retrofitAuthServiceClient.authToken(
                        "client_credentials", //Use the client_credentials authentication method
                        ApiUser.getAuthKeys()) //Get the keys used for authenticating with the OAuth endpoint
                        .finallyDo(() -> fetchingToken = 0)
                        .subscribe(ApiUser.authTokens::updateTokens); //Update the cached token with the new one
            } catch (UnsupportedEncodingException e) {
                e.printStackTrace();
            }
        }
        while (fetchingToken > 0) {
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
        request.addHeader("Authorization", user.getBearerToken()); //Add the cached token to the authorization header
    }
};
```
You can see here that observables (as well as Java 8 lambdas) can make your code shorter and easier to understand.

#Conclusions
There are (at least) three different approaches that can be used when working with Retrofit to perform network requests in you Android application. Of these options, I find that RxJava observables (using RxAndroid) are the most powerful, with callbacks as a close second. I also recommend that whatever method you decide to use, stick with it for everything in the application in order to avoid strange bugs from race conditions between the different implementations.
