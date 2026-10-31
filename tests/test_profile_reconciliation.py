import hashlib
import json
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
CURRENT=ROOT/"contracts"/"editor-syntax"/"v1"/"editor-lexical-contract.json"
TARGET=ROOT/"conformance"/"oreslang-syntax-v1.json"
BRIDGE=ROOT/"contracts"/"editor-syntax"/"v1"/"profile-reconciliation.json"

def git_blob(path):
    raw=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

class ExplicitLexicalProfiles(unittest.TestCase):
    def test_exact_profiles_and_nonpromotion(self):
        current=json.loads(CURRENT.read_text(encoding="utf-8"))
        target=json.loads(TARGET.read_text(encoding="utf-8"))
        bridge=json.loads(BRIDGE.read_text(encoding="utf-8"))
        self.assertEqual(bridge["schema"],"oreslang.editor-syntax-profile-reconciliation/v1")
        self.assertEqual(bridge["resolution"]["mergeGate"],"BLOCKED_COMPILER_PARITY")
        self.assertEqual(bridge["resolution"]["activeStackedEditorProfile"],"language-target")
        self.assertTrue(bridge["resolution"]["explicitlyNotEquivalent"])
        self.assertEqual(git_blob(CURRENT),bridge["profiles"]["compiler-current"]["gitBlobSha"])
        self.assertEqual(git_blob(TARGET),bridge["profiles"]["language-target"]["gitBlobSha"])
        for word in bridge["profiles"]["compiler-current"]["reservedComparisonWords"]:
            self.assertIn(word,current["reservedWords"])
            self.assertIn(word,target["profiles"]["editorTarget"]["contextualIdentifierWords"])
        for word in bridge["profiles"]["compiler-current"]["reservedLegacyWords"]:
            self.assertIn(word,current["reservedWords"])
            self.assertIn(word,target["profiles"]["editorTarget"]["excludedReservedWords"])
        for char in bridge["profiles"]["compiler-current"]["operatorTokenCharacters"]:
            self.assertIn(char,current["operatorTokenCharacters"])
            self.assertIn(char,target["profiles"]["editorTarget"]["excludedArithmeticOperators"])
        self.assertIn("^^",target["profiles"]["editorTarget"]["excludedArithmeticOperators"])
        self.assertEqual(bridge["authority"]["lexerBlobSha"],current["compilerSnapshot"]["lexerBlobSha"])
        self.assertEqual(bridge["authority"]["tokenBlobSha"],current["compilerSnapshot"]["tokenBlobSha"])
        self.assertEqual(bridge["authority"]["grammarBlobSha"],current["compilerSnapshot"]["grammarBlobSha"])
        self.assertEqual(target["authority"]["repo"],bridge["authority"]["repository"])
        self.assertEqual(len(target["cases"]),50)
        self.assertEqual(len(bridge["differenceIds"]),6)

if __name__=="__main__":
    unittest.main()
