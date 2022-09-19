import json
import logging

import requests

from azbankgateways.banks import BaseBank
from azbankgateways.exceptions import SettingDoesNotExist, BankGatewayConnectionError
from azbankgateways.exceptions.exceptions import BankGatewayRejectPayment
from azbankgateways.models import CurrencyEnum, BankType, PaymentStatus
from azbankgateways.utils import get_json, split_to_dict_querystring


class Pay(BaseBank):
    _api = None
    _params = {}

    def __init__(self, **kwargs):
        super(Pay, self).__init__(**kwargs)
        self.set_gateway_currency(CurrencyEnum.IRR)
        self._token_api_url = 'https://pay.ir/payment/send'
        self._payment_url = 'https://pay.ir/payment/gateway/{token}'
        self._verify_api_url = 'https://pay.ir/payment/verify'

    def get_bank_type(self):
        return BankType.PAY

    def set_default_settings(self):
        for item in ['API']:
            if item not in self.default_setting_kwargs:
                raise SettingDoesNotExist()
            setattr(self, f'_{item.lower()}', self.default_setting_kwargs[item])

    """
    gateway
    """

    def _get_gateway_payment_url_parameter(self):
        return self._payment_url

    def prepare_verify_from_gateway(self):
        params = {}
        params.update(self._params)
        return params

    def _get_gateway_payment_parameter(self):
        params = {}
        # status token
        return params

    def _get_gateway_payment_method_parameter(self):
        return "GET"

    """
    pay
    """

    def get_pay_data(self):
        data = {
            'api': self._api,
            'amount': self.get_gateway_amount(),
            'redirect': self._get_gateway_callback_url(),
            'mobile': self.get_mobile_number(),
            'factorNumber': self.get_tracking_code(),
        }
        return data

    def prepare_pay(self):
        super(Pay, self).prepare_pay()

    def pay(self):
        super(Pay, self).pay()
        data = self.get_pay_data()
        response_json = self._send_data(self._token_api_url, data)
        if response_json['status'] == 1:
            self._payment_url = self._payment_url.format(token=response_json['token'])
            self._set_reference_number(response_json['token'])
        else:
            logging.critical("Pay gateway reject payment")
            raise BankGatewayRejectPayment(self.get_transaction_status_text())

    """
    verify
    """

    def get_verify_data(self):
        super(Pay, self).get_verify_data()
        data = {
            'api': self._api,
            'token': self.get_reference_number(),
        }
        return data

    def prepare_verify(self, tracking_code):
        super(Pay, self).prepare_verify(tracking_code)

    def verify(self, tracking_code):
        super(Pay, self).verify(tracking_code)
        data = self.get_verify_data()
        response_json = self._send_data(self._verify_api_url, data, timeout=10)
        if response_json.get('status', 0) == 1:
            self._set_payment_status(PaymentStatus.COMPLETE)
            extra_information = json.dumps(response_json)
            self._bank.extra_information = extra_information
            self._bank.save()
        else:
            self._set_payment_status(PaymentStatus.CANCEL_BY_USER)
            logging.debug("Pay gateway unapprove payment")

    """
    other methods
    """

    def _send_data(self, url, data, timeout=5):
        headers = {
            'api': self._api,
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=timeout)
        except requests.Timeout:
            logging.exception("Pay time out gateway {}".format(data))
            raise BankGatewayConnectionError()
        except requests.ConnectionError:
            logging.exception("Pay time out gateway {}".format(data))
            raise BankGatewayConnectionError()

        response_json = get_json(response)
        if 'errorMessage' in response_json:
            self._set_transaction_status_text(response_json['errorMessage'])
        return response_json
