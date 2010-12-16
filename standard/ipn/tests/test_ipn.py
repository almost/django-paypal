from django.conf import settings
from django.http import HttpResponse
from django.test import TestCase
from django.test.client import Client

from paypal.standard.ipn.models import PayPalIPN
from paypal.standard.ipn.signals import (payment_was_successful, 
    payment_was_flagged)


IPN_POST_PARAMS = {
    "protection_eligibility": "Ineligible",
    "last_name": "User",
    "txn_id": "VH153354B51403485",
    "receiver_email": settings.PAYPAL_RECEIVER_EMAIL,
    "payment_status": "Completed",
    "payment_gross": "10.00",
    "tax": "0.00",
    "residence_country": "US",
    "invoice": "0004",
    "payer_status": "verified",
    "txn_type": "express_checkout",
    "handling_amount": "0.00",
    "payment_date": "23:04:06 Feb 02, 2009 PST",
    "first_name": "Test",
    "item_name": "",
    "charset": "windows-1252",
    "custom": "website_id=13&user_id=21",
    "notify_version": "2.6",
    "transaction_subject": "",
    "test_ipn": "1",
    "item_number": "",
    "receiver_id": "258DLEHY2BDK6",
    "payer_id": "BN5JZ2V7MLEV4",
    "verify_sign": "An5ns1Kso7MWUdW4ErQKJJJ4qi4-AqdZy6dD.sGO3sDhTf1wAbuO2IZ7",
    "payment_fee": "0.59",
    "mc_fee": "0.59",
    "mc_currency": "USD",
    "shipping": "0.00",
    "payer_email": "bishan_1233269544_per@gmail.com",
    "payment_type": "instant",
    "mc_gross": "10.00",
    "quantity": "1",
}

IPN_POST_PARAMS_AUCTION = {
    'protection_eligibility': 'Eligible',
    'last_name': 'Gaarden',
    'txn_id': '14D96004MF8903031',
    'shipping_method': 'Default',
    'shipping_discount': '0.00',
    'receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
    'payment_status': 'Completed',
    'payment_gross': '',
    'tax': '0.00',
    'item_name1': 'The Test Item',
    'residence_country': 'US',
    'address_state': 'PA',
    'payer_status': 'verified',
    'txn_type': 'cart',
    'num_cart_items': '1',
    'address_street': '21 test street',
    'verify_sign': '1NtHArKmjsNN95vdQiJQa6JXSPocybl6Aenv7jf0wuCOcAU.',
    'payment_date': '11:26:03 Oct 05, 2010 PDT',
    'first_name': 'Test',
    'mc_shipping': '0.00',
    'item_name': 'The Test Item',
    'item_number1': '1234567890',
    'charset': 'UTF-8',
    'custom': '',
    'notify_version': '3.0',
    'address_name': 'Test Name',
    'for_auction': 'true',
    'mc_gross_1': '14.95',
    'contact_phone': '123 12345678',
    'item_number': '1234567890',
    'receiver_id': '258DLEHY2BDK6',
    'transaction_subject': '',
    'business': 'test@example.com',
    'payer_id': '258DLEHY2BDK6',
    'mc_handling1': '0.00',
    'discount': '0.00',
    'tax1': '0.00',
    'auction_closing_date': '04:24:07 Oct 05, 2010 PDT',
    'mc_handling': '0.00',
    'auction_buyer_id': 'thebuyer',
    'address_zip': '12345',
    'payment_fee': '',
    'address_country_code': 'US',
    'address_city': 'Somecity',
    'address_status': 'confirmed',
    'insurance_amount': '0.00',
    'quantity1': '1',
    'address_country': 'United States',
    'mc_fee': '0.78',
    'mc_currency': 'USD',
    'payer_email': 'test2@example.com',
    'payment_type': 'instant',
    'mc_gross': '14.95',
    'mc_shipping1': '0.00'
}


class IPNTest(TestCase):    
    urls = 'paypal.standard.ipn.tests.test_urls'

    def setUp(self):
        self.old_debug = settings.DEBUG
        settings.DEBUG = True

        # Monkey patch over PayPalIPN to make it get a VERFIED response.
        self.old_postback = PayPalIPN._postback
        PayPalIPN._postback = lambda self: "VERIFIED"

        # Remove any receivers on the signals, these can cause the
        # tests to fail if other apps have registered handlers.
        payment_was_successful.receivers = []
        payment_was_flagged.receivers = []
        
    def tearDown(self):
        settings.DEBUG = self.old_debug
        PayPalIPN._postback = self.old_postback

    def assertGotSignal(self,signal, flagged):
        # Check the signal was sent. These get lost if they don't reference self.
        self.got_signal = False
        self.signal_obj = None
        
        def handle_signal(sender, **kwargs):
            self.got_signal = True
            self.signal_obj = sender
        signal.connect(handle_signal)
        
        response = self.client.post("/ipn/", IPN_POST_PARAMS)
        self.assertEqual(response.status_code, 200)
        ipns = PayPalIPN.objects.all()
        self.assertEqual(len(ipns), 1)        
        ipn_obj = ipns[0]        
        self.assertEqual(ipn_obj.flag, flagged)
        
        self.assertTrue(self.got_signal)
        self.assertEqual(self.signal_obj, ipn_obj)
        
    def test_correct_ipn(self):
        self.assertGotSignal(payment_was_successful, False)

    def test_failed_ipn(self):
        PayPalIPN._postback = lambda self: "INVALID"
        self.assertGotSignal(payment_was_flagged, True)

    def assertFlagged(self, updates, flag_info):
        params = IPN_POST_PARAMS.copy()
        params.update(updates)
        response = self.client.post("/ipn/", params)
        self.assertEqual(response.status_code, 200)
        ipn_obj = PayPalIPN.objects.all()[0]
        self.assertEqual(ipn_obj.flag, True)
        self.assertEqual(ipn_obj.flag_info, flag_info)

    def test_incorrect_receiver_email(self):
        update = {"receiver_email": "incorrect_email@someotherbusiness.com"}
        flag_info = "Invalid receiver_email. (incorrect_email@someotherbusiness.com)"
        self.assertFlagged(update, flag_info)

    def test_invalid_payment_status(self):
        update = {"payment_status": "Failed"}
        flag_info = "Invalid payment_status. (Failed)"
        self.assertFlagged(update, flag_info)

    def test_duplicate_txn_id(self):       
        self.client.post("/ipn/", IPN_POST_PARAMS)
        self.client.post("/ipn/", IPN_POST_PARAMS)
        self.assertEqual(len(PayPalIPN.objects.all()), 2)
        ipn_obj = PayPalIPN.objects.order_by('-created_at')[0]
        self.assertEqual(ipn_obj.flag, True)
        self.assertEqual(ipn_obj.flag_info, "Duplicate txn_id. (VH153354B51403485)")

    def test_non_auction_ipn(self):
        self.client.post("/ipn/", IPN_POST_PARAMS)
        self.assertEqual(len(PayPalIPN.objects.all()), 1)
        ipn_obj = PayPalIPN.objects.all()[0]
        self.assertEqual(ipn_obj.flag, False)
        self.assertFalse(ipn_obj.for_auction)
        

    def test_auction_ipn(self):
        self.client.post("/ipn/", IPN_POST_PARAMS_AUCTION)
        self.assertEqual(len(PayPalIPN.objects.all()), 1)
        ipn_obj = PayPalIPN.objects.all()[0]
        self.assertTrue(ipn_obj.for_auction)
        self.assertEqual(ipn_obj.flag, False)
        self.assertEqual(ipn_obj.item_number, "1234567890")
