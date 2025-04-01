#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Function.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/raw_ostream.h"

#include <fstream>
#include <sstream>
#include <string>
#include <map>
#include <algorithm>
#include <cctype>
#include <locale>

using namespace llvm;

//===----------------------------------------------------------------------===//
// Command-line option for the CSV file path.
//===----------------------------------------------------------------------===//
static cl::opt<std::string> CSVFilePath(
    "rename-csv",
    cl::desc("Specify CSV file with mappings in the format: old,new"),
    cl::value_desc("filename"));

//===----------------------------------------------------------------------===//
// Helper functions for whitespace trimming.
//===----------------------------------------------------------------------===//

// trim from start (in place)
static inline void ltrim(std::string &s) {
  s.erase(s.begin(),
          std::find_if(s.begin(), s.end(), [](unsigned char ch) {
            return !std::isspace(ch);
          }));
}

// trim from end (in place)
static inline void rtrim(std::string &s) {
  s.erase(std::find_if(s.rbegin(), s.rend(), [](unsigned char ch) {
            return !std::isspace(ch);
          }).base(),
          s.end());
}

// trim from both ends (in place)
static inline void trim(std::string &s) {
  ltrim(s);
  rtrim(s);
}

//===----------------------------------------------------------------------===//
// CSV Parsing: Reads the CSV file and returns a mapping of old names to new names.
//===----------------------------------------------------------------------===//
std::map<std::string, std::string> parseCSV(const std::string &filePath) {
  std::map<std::string, std::string> renameMap;
  std::ifstream file(filePath);
  if (!file.is_open()) {
    errs() << "Error opening CSV file: " << filePath << "\n";
    return renameMap; // Return an empty map in case of error.
  }

  std::string line;
  while (std::getline(file, line)) {
    if (line.empty())
      continue;
    std::istringstream iss(line);
    std::string oldName, newName;
    if (std::getline(iss, oldName, ',') && std::getline(iss, newName, ',')) {
      trim(oldName);
      trim(newName);
      if (!oldName.empty() && !newName.empty())
        renameMap[oldName] = newName;
    }
  }
  file.close();
  return renameMap;
}

//===----------------------------------------------------------------------===//
// FunctionRenamerPass: ModulePass using the new pass manager.
//===----------------------------------------------------------------------===//
struct FunctionRenamerPass : public PassInfoMixin<FunctionRenamerPass> {
  // Main entry point - runs the pass over the module.
  PreservedAnalyses run(Module &M, ModuleAnalysisManager &AM) {
    // Parse the CSV file using the command-line option.
    std::map<std::string, std::string> renameMap = parseCSV(CSVFilePath);
    if (renameMap.empty()) {
      errs() << "No valid mappings found. Ensure the CSV file is correctly formatted.\n";
      // Nothing was modified, so we preserve all analyses.
      return PreservedAnalyses::all();
    }

    bool modified = false;
    // Iterate over all functions in the module.
    for (Function &F : M) {
      // Skip function declarations (i.e., functions without a body).
      if (F.isDeclaration())
        continue;

      std::string currentName = F.getName().str();
      auto it = renameMap.find(currentName);
      if (it != renameMap.end()) {
        std::string newName = it->second;
        F.setName(newName);
        modified = true;
        errs() << "Renamed function \"" << currentName << "\" to \"" << newName << "\"\n";
      }
    }

    // Return which analyses are preserved.
    return modified ? PreservedAnalyses::none() : PreservedAnalyses::all();
  }
};

//===----------------------------------------------------------------------===//
// Pass Plugin Registration
// This boilerplate is used to register the pass with the LLVM pass manager.
//===----------------------------------------------------------------------===//
extern "C" LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo llvmGetPassPluginInfo() {
  return {
      LLVM_PLUGIN_API_VERSION, "FunctionRenamerPass", "v0.1",
      [](PassBuilder &PB) {
        // Register our pass as a module pass.
        PB.registerPipelineParsingCallback(
            [](StringRef Name, ModulePassManager &MPM,
               ArrayRef<PassBuilder::PipelineElement>) {
              if (Name == "function-renamer") {
                MPM.addPass(FunctionRenamerPass());
                return true;
              }
              return false;
            });
      }};
}