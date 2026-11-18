package com.paymesh.backend.chat;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class ChatContractTest {
 @Test void approvedRulesMatchActualPythonFixtures()throws Exception{var json=new ObjectMapper();try(var input=getClass().getResourceAsStream("/ai-chat/python-fixtures.json")){var cases=json.readTree(input);assertTrue(cases.size()>40);for(var item:cases){var expected=ChatRules.expected(item.get("request"));var actual=item.get("response");assertEquals(actual.path("answer").asText(),expected.answer(),item.path("request").path("question").asText());assertEquals(actual.path("intent").asText(),expected.intent());assertEquals(actual.get("moneyFacts"),json.readTree(expected.money().toString()));assertEquals(actual.get("evidenceReferences"),json.valueToTree(expected.refs()));assertEquals(actual.get("limitations"),json.valueToTree(expected.limitations()));}}}
 @Test void strictInputAndPrivacy(){assertThrows(ChatFailure.class,()->ChatDtos.validate(new ChatDtos.Input("what status?",java.util.Arrays.asList((ChatDtos.Message)null),null)));assertThrows(ChatFailure.class,()->ChatDtos.validate(new ChatDtos.Input("password=never-send",null,null)));assertThrows(ChatFailure.class,()->ChatDtos.validate(new ChatDtos.Input("customer@example.test status",null,null)));assertThrows(ChatFailure.class,()->ChatDtos.validate(new ChatDtos.Input("x".repeat(1001),null,null)));}
}
