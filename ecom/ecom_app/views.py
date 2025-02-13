from django.shortcuts import render
from ecom_app.models import Product
from math import ceil
from ecom_app import keys

# Create your views here.
def home(request):
    return render(request, 'index.html')

def purchase(request):
    current_user = request.user
    print(current_user)
    allProds = []
    catprods = Product.objects.values('category', 'id')
    cats = {item['category'] for item in catprods}
    for cat in cats:
        prod = Product.objects.filter(category = cat)
        n = len(prod)
        nSlides = n // 4 + ceil((n / 4) - (n // 4))
        allProds.append([prod, range(1, nSlides), nSlides])

    params = {'allProds': allProds}
    return render(request, 'purchase.html', params)

def checkout(request):
    if not request.user.is_authenticated:
        messages.warning(request, "login & Try Again")
        return redirect('/ecom_auth/login')
    
    return render(request, 'checkout.html')
