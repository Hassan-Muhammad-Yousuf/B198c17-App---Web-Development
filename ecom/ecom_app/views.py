from django.shortcuts import render, redirect, HttpResponse
from ecom_app.models import Product, Orders, OrderUpdate
from math import ceil
from ecom_app import keys
from django.contrib import messages
import stripe
import json

stripe.api_key = keys.STRIPE_SECRET_KEY

# Create your views here.
def home(request):
    return render(request, 'index.html')

def tracker(request):
    if not request.user.is_authenticated:
        messages.warning(request, "Login & Try Again")
        return redirect('/ecom_auth/login')
    if request.method == "POST":
        orderId = request.POST.get('orderId', '')
        email = request.POST.get('email', '')
        try:
            order = Orders.objects.filter(order_id=orderId, email=email)
            if len(order) > 0:
                update = OrderUpdate.objects.filter(order_id=orderId)
                updates = []
                for item in update:
                    updates.append({'text': item.update_desc, 'time': item.timestamp})
                response = json.dumps([updates, order[0].items_json], default=str)
                return HttpResponse(response)
            else:
                return HttpResponse('{}')
        except Exception as e:
            return HttpResponse('{}')
        
    return render(request, 'tracker.html')

def purchase(request):
    allProds = []
    catprods = Product.objects.values('category', 'id')
    cats = {item['category'] for item in catprods}
    for cat in cats:
        prod = Product.objects.filter(category=cat)
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
        # Capture form data
        item_json = request.POST.get('itemJson', '')
        first_name = request.POST.get('firstName', '')
        last_name = request.POST.get('lastName', '')
        name = f"{first_name} {last_name}"
        amount = request.POST.get('amt', '')
        email = request.POST.get('email', '')
        address1 = request.POST.get('address', '')
        address2 = request.POST.get('address2', '')  # Capture address line 2
        city = request.POST.get('city', '')  # Capture city
        state = request.POST.get('state', '')
        zip_code = request.POST.get('zip', '')
        phone = request.POST.get('phone', '')  # Capture phone number

        # Validate form data
        if not all([first_name, last_name, email, address1, state, zip_code, phone]):
            messages.error(request, "Please fill out all required fields.")
            return redirect('Checkout')
        
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

        # Generate a more readable OID
        # Extract the first product name from the items_json
        cart_items = json.loads(item_json)
        first_product_id = next(iter(cart_items), None)
        product_name = "Order"
        if first_product_id:
            product_name = cart_items[first_product_id][1].split()[0]  # Get first word of product name
        
        readable_oid = f"{product_name}-{order.order_id}"
        order.oid = readable_oid
        order.save()

        # Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {
                            'name': f'Order #{order.order_id}: {product_name}',
                        },
                        'unit_amount': order.amount,  # in cents
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=request.build_absolute_uri('/success/') + '?session_id={CHECKOUT_SESSION_ID}&order_id=' + str(order.order_id),
            cancel_url=request.build_absolute_uri('/cancel/'),
            metadata={
                'order_id': order.order_id,
                'readable_oid': readable_oid,
            }
        )

        return redirect(checkout_session.url, code=303)

    return render(request, 'checkout.html')

def payment_success(request):
    session_id = request.GET.get('session_id')
    order_id = request.GET.get('order_id')
    
    if not session_id:
        messages.error(request, 'Invalid payment session.')
        return redirect('/')
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        order_id = session.metadata.get('order_id')
        readable_oid = session.metadata.get('readable_oid')
        
        order = Orders.objects.get(order_id=order_id)
        order.paymentpaid = 'Paid'
        order.amountpaid = session.amount_total / 100  # Convert cents to dollars
        order.oid = readable_oid or session_id  # Use readable OID if available
        order.save()
        
        # Add a payment success update
        update = OrderUpdate(order_id=order.order_id, update_desc="Payment successful, order confirmed")
        update.save()
        
        messages.success(request, f'Payment Successful! Your order ID is {order.oid}')
        
        # Clear the cart in localStorage
        return render(request, 'payment_success.html', {'order': order})
    except Exception as e:
        messages.error(request, f'Error processing payment: {str(e)}')
        return redirect('/')

def payment_cancel(request):
    messages.error(request, 'Payment Cancelled. Your order is saved, but not confirmed. Try again.')
    return redirect('/checkout/')