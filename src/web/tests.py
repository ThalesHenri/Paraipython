from django.test import TestCase, override_settings
from django.urls import reverse

from web.pix import crc16_ccitt, payload_pix

APOIO_REAL = {
    "PIX_CHAVE": "+5583999990000",
    "PIX_NOME": "Fulano de Tal da Silva Sauro",
    "PIX_CIDADE": "João Pessoa",
    "PIX_DESCRICAO": "",
    "PIX_QR_IMAGEM": "",
    "LINK_NOME": "Apoia.se",
    "LINK_URL": "",
    "FICTICIO": False,
}


class PixTest(TestCase):
    def test_crc_bate_com_exemplo_do_manual_do_bcb(self):
        exemplo = (
            "00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-426655440000"
            "5204000053039865802BR5913Fulano de Tal6008BRASILIA62070503***6304"
        )
        self.assertEqual(crc16_ccitt(exemplo), "1D3D")

    def test_payload_estatico(self):
        codigo = payload_pix("+5583999990000", "Fulano de Tal da Silva Sauro", "João Pessoa")
        self.assertTrue(codigo.startswith("000201"))
        self.assertIn("0014br.gov.bcb.pix0114+5583999990000", codigo)
        self.assertIn("5925FULANO DE TAL DA SILVA S", codigo)  # nome cortado em 25
        self.assertIn("6011JOAO PESSOA", codigo)                # sem acento
        self.assertIn("53039865802BR", codigo)                  # sem valor fixo (campo 54)
        self.assertEqual(codigo[-4:], crc16_ccitt(codigo[:-4]))

    def test_payload_com_valor(self):
        self.assertIn("54045.00", payload_pix("a@b.com", "X", "Y", valor=5))


class SobreApoieTest(TestCase):
    def test_dados_ficticios_mostram_aviso(self):
        resp = self.client.get(reverse("web:sobre"))
        self.assertContains(resp, "Pague um cafezinho pro robô")
        self.assertContains(resp, "Dados de exemplo")
        self.assertContains(resp, "chave-ficticia@expressopb.exemplo")
        self.assertContains(resp, "data:image/svg+xml;base64,")

    @override_settings(APOIO=APOIO_REAL)
    def test_dados_reais_sem_aviso_e_sem_link(self):
        resp = self.client.get(reverse("web:sobre"))
        self.assertNotContains(resp, "Dados de exemplo")
        self.assertContains(resp, "+5583999990000")
        self.assertNotContains(resp, "Apoiar todo mês")

    @override_settings(APOIO={**APOIO_REAL, "PIX_QR_IMAGEM": "img/meu-pix.png"})
    def test_imagem_do_banco_tem_prioridade(self):
        resp = self.client.get(reverse("web:sobre"))
        self.assertContains(resp, "/static/img/meu-pix.png")
