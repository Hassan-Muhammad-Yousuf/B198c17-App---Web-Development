from django.shortcuts import render, redirect
from ecom_app.models import Product,Orders,OrderUpdate
from math import ceil
from ecom_app import keys
from django.contrib import messages
import stripe

stripe.api_key = keys.STRIPE_SECRET_KEY

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
        messages.warning(request, "Login & Try Again")
        return redirect('/ecom_auth/login')

    if request.method == "POST":
        item_json = request.POST.get('itemJson', '')
        name = request.POST.get('firstName', '') + ' ' + request.POST.get('lastName', '')
        amount = request.POST.get('amt', '')
        email = request.POST.get('email', '')
        address1 = request.POST.get('address', '')
        address2 = ""
        city = ""
        state = request.POST.get('state', '')
        zip_code = request.POST.get('zip', '')
        phone = ""

        # Create the order in DB
        order = Orders(
            items_json=item_json,
            name=name,
            amount=int(float(amount) * 100),  # Amount in cents
            email=email,
            address1=address1,
            address2=address2,
            city=city,
            state=state,
            zip_code=zip_code,
            phone=phone,
        )
        order.save()

        # Create Order Update
        update = OrderUpdate(order_id=order.order_id, update_desc="Order has been placed")
        update.save()

        # Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {
                            'name': 'Order #{}'.format(order.order_id),
                        },
                        'unit_amount': order.amount,  # in cents
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=request.build_absolute_uri('/success/') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri('/cancel/'),
            metadata={
                'order_id': order.order_id,
            }
        )

        return redirect(checkout_session.url, code=303)

    return render(request, 'checkout.html')


def payment_success(request):
    session_id = request.GET.get('session_id')
    session = stripe.checkout.Session.retrieve(session_id)

    order_id = session.metadata.get('order_id')
    order = Orders.objects.get(order_id=order_id)

    order.paymentpaid = 'Paid'
    order.amountpaid = session.amount_total / 100  # Convert cents to dollars
    order.oid = session_id
    order.save()

    messages.success(request, f'Payment Successful! Order ID: {order_id}')
    return redirect('/')


def payment_cancel(request):
    messages.error(request, 'Payment Cancelled. Try again.')
    return redirect('/checkout/')
