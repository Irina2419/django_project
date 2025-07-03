from django.shortcuts import render
from django.http import HttpResponse # Add this line

def index(request):
    return HttpResponse("Hello, world! This is my first Django app.")