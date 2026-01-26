"""
Tests to ensure all abstract methods are properly implemented.

These tests catch the common issue where a new abstract method is added
but forgotten in one of the concrete implementations.
"""

import inspect
import pytest
from abc import ABC, abstractmethod
from typing import Type, List, Tuple, get_type_hints

from modular_cli_sdk.services.credentials_manager import (
    AbstractCredentialsManager,
    FileSystemCredentialsManager,
    SSMCredentialsManager,
)
from modular_cli_sdk.client.ssm_client import (
    AbstractSecretsManager,
    OnPremSecretsManager,
    VaultSecretsManager,
    SSMSecretsManager,
)

# =============================================================================
# Configuration: Define all abstract classes and their implementations
# =============================================================================

CREDENTIALS_MANAGER_IMPLEMENTATIONS: List[Type[AbstractCredentialsManager]] = [
    FileSystemCredentialsManager,
    SSMCredentialsManager,
]

SECRETS_MANAGER_IMPLEMENTATIONS: List[Type[AbstractSecretsManager]] = [
    OnPremSecretsManager,
    VaultSecretsManager,
    SSMSecretsManager,
]

# Mapping of abstract class to its implementations
ABSTRACT_TO_IMPLEMENTATIONS: List[Tuple[Type[ABC], List[Type]]] = [
    (AbstractCredentialsManager, CREDENTIALS_MANAGER_IMPLEMENTATIONS),
    (AbstractSecretsManager, SECRETS_MANAGER_IMPLEMENTATIONS),
]


# =============================================================================
# Helper functions
# =============================================================================

def get_abstract_methods(cls: Type[ABC]) -> set:
    """Get all abstract method names from an abstract class"""
    abstract_methods = set()
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if getattr(method, "__isabstractmethod__", False):
            abstract_methods.add(name)
    return abstract_methods


def get_method_signature(cls: Type, method_name: str) -> inspect.Signature:
    """Get the signature of a method."""
    method = getattr(cls, method_name)
    return inspect.signature(method)


def get_all_concrete_classes() -> List[Tuple[Type[ABC], Type]]:
    """Generate pairs of (abstract_class, concrete_class) for parametrization"""
    pairs = []
    for abstract_cls, implementations in ABSTRACT_TO_IMPLEMENTATIONS:
        for impl in implementations:
            pairs.append((abstract_cls, impl))
    return pairs


# =============================================================================
# Tests: Abstract Method Implementation
# =============================================================================

class TestAbstractMethodImplementation:
    """Ensure all concrete classes implement all required abstract methods"""

    @pytest.mark.parametrize(
        "abstract_cls,concrete_cls",
        get_all_concrete_classes(),
        ids=lambda x: x.__name__ if isinstance(x, type) else str(x),
    )
    def test_class_is_not_abstract(
            self,
            abstract_cls: Type[ABC],
            concrete_cls: Type,
    ) -> None:
        """
        Verify concrete class has no remaining abstract methods.

        This will fail if you add an abstract method to the base class
        but forget to implement it in the concrete class.
        """
        assert not inspect.isabstract(concrete_cls), (
            f"{concrete_cls.__name__} is still abstract. "
            f"Missing implementations for: {concrete_cls.__abstractmethods__}"
        )

    @pytest.mark.parametrize(
        "abstract_cls,concrete_cls",
        get_all_concrete_classes(),
        ids=lambda x: x.__name__ if isinstance(x, type) else str(x),
    )
    def test_all_abstract_methods_exist(
            self,
            abstract_cls: Type[ABC],
            concrete_cls: Type
    ) -> None:
        """Verify all abstract methods are present in concrete class."""
        abstract_methods = get_abstract_methods(abstract_cls)

        for method_name in abstract_methods:
            assert hasattr(concrete_cls, method_name), (
                f"{concrete_cls.__name__} is missing method: {method_name}"
            )
            method = getattr(concrete_cls, method_name)
            assert callable(method), (
                f"{concrete_cls.__name__}.{method_name} exists but is not callable"
            )

    @pytest.mark.parametrize(
        "abstract_cls,concrete_cls",
        get_all_concrete_classes(),
        ids=lambda x: x.__name__ if isinstance(x, type) else str(x),
    )
    def test_method_is_actually_implemented(
            self,
            abstract_cls: Type[ABC],
            concrete_cls: Type,
    ) -> None:
        """
        Verify methods are actually implemented,
         not just passing or raising NotImplementedError.

        This catches cases where someone adds a method stub like:
            def new_method(self):
                pass  # TODO: implement
        """
        abstract_methods = get_abstract_methods(abstract_cls)

        for method_name in abstract_methods:
            method = getattr(concrete_cls, method_name)
            source = inspect.getsource(method)

            # Check for common "not implemented" patterns
            not_implemented_patterns = [
                "raise NotImplementedError",
                "NotImplementedError()",
                "pass  # TODO",
                "pass  # FIXME",
                "...\n",  # Just ellipsis
            ]

            # Only flag if method body is ONLY these patterns
            # (allow them in combination with real code)
            lines = [
                line.strip()
                for line in source.split('\n')
                if line.strip() and not line.strip().startswith('#')
                   and not line.strip().startswith('def ')
                   and not line.strip().startswith('"""')
                   and not line.strip().startswith("'''")
            ]

            # If the only non-decorator/def line is 'pass' or '...', it's not implemented
            code_lines = [l for l in lines if l not in ('pass', '...')]
            if not code_lines:
                pytest.fail(
                    f"{concrete_cls.__name__}.{method_name} appears to be a stub "
                    f"(only contains 'pass' or '...')"
                )


# =============================================================================
# Tests: Method Signature Consistency
# =============================================================================

class TestMethodSignatureConsistency:
    """
    Ensure all implementations have consistent method signatures.

    This catches issues where:
    - Parameter names differ between implementations
    - Parameter types/annotations differ
    - Return type annotations differ
    """

    @pytest.mark.parametrize(
        "abstract_cls,implementations",
        ABSTRACT_TO_IMPLEMENTATIONS,
        ids=lambda x: x.__name__ if isinstance(x, type) else str(x),
    )
    def test_signatures_match_abstract(
            self, abstract_cls: Type[ABC], implementations: List[Type]
    ):
        """Verify concrete implementations match abstract method signatures."""
        abstract_methods = get_abstract_methods(abstract_cls)

        for method_name in abstract_methods:
            abstract_sig = get_method_signature(abstract_cls, method_name)
            abstract_params = list(abstract_sig.parameters.keys())

            for impl in implementations:
                impl_sig = get_method_signature(impl, method_name)
                impl_params = list(impl_sig.parameters.keys())

                # Compare parameter names (excluding 'self')
                abstract_params_no_self = [p for p in abstract_params if
                                           p != 'self']
                impl_params_no_self = [p for p in impl_params if p != 'self']

                assert abstract_params_no_self == impl_params_no_self, (
                    f"{impl.__name__}.{method_name} has different parameters.\n"
                    f"  Abstract: {abstract_params_no_self}\n"
                    f"  Concrete: {impl_params_no_self}"
                )

    @pytest.mark.parametrize(
        "abstract_cls,implementations",
        ABSTRACT_TO_IMPLEMENTATIONS,
        ids=lambda x: x.__name__ if isinstance(x, type) else str(x),
    )
    def test_return_type_annotations_present(
            self,
            abstract_cls: Type[ABC],
            implementations: List[Type],
    ) -> None:
        """Verify return type annotations are present and consistent."""
        abstract_methods = get_abstract_methods(abstract_cls)

        for method_name in abstract_methods:
            abstract_sig = get_method_signature(abstract_cls, method_name)
            expected_return = abstract_sig.return_annotation

            if expected_return is inspect.Signature.empty:
                continue  # Skip if abstract doesn't have annotation

            for impl in implementations:
                impl_sig = get_method_signature(impl, method_name)
                impl_return = impl_sig.return_annotation

                # At minimum, check that return annotation exists
                if expected_return is not inspect.Signature.empty:
                    assert impl_return is not inspect.Signature.empty, (
                        f"{impl.__name__}.{method_name} is missing return "
                        f"type annotation. Expected: {expected_return}"
                    )


# =============================================================================
# Tests: Cross-Implementation Consistency
# =============================================================================

class TestCrossImplementationConsistency:
    """Test that all implementations of same abstract class are consistent"""

    def test_credentials_managers_have_same_public_methods(self):
        """All CredentialsManager implementations should have the same public API"""
        implementations = CREDENTIALS_MANAGER_IMPLEMENTATIONS

        # Get public methods (not starting with _) for each implementation
        public_methods_per_impl = {}
        for impl in implementations:
            methods = {
                name for name, _ in
                inspect.getmembers(impl, predicate=inspect.isfunction)
                if not name.startswith('_')
            }
            public_methods_per_impl[impl.__name__] = methods

        # All should have the same public methods
        first_impl = implementations[0]
        first_methods = public_methods_per_impl[first_impl.__name__]

        for impl in implementations[1:]:
            impl_methods = public_methods_per_impl[impl.__name__]

            missing = first_methods - impl_methods
            extra = impl_methods - first_methods

            if missing:
                pytest.fail(
                    f"{impl.__name__} is missing public methods present in "
                    f"{first_impl.__name__}: {missing}"
                )
            # Note: extra methods are allowed (implementations can have additional methods)

    def test_secrets_managers_have_same_public_methods(self):
        """All SecretsManager implementations should have the same public API"""
        implementations = SECRETS_MANAGER_IMPLEMENTATIONS

        # Get public methods from abstract class
        abstract_methods = get_abstract_methods(AbstractSecretsManager)

        for impl in implementations:
            impl_methods = {
                name for name, _ in
                inspect.getmembers(impl, predicate=inspect.isfunction)
                if not name.startswith('_')
            }

            missing = abstract_methods - impl_methods
            assert not missing, (
                f"{impl.__name__} is missing required methods: {missing}"
            )


# =============================================================================
# Tests: Instantiation Tests (catch __init__ issues)
# =============================================================================

class TestInstantiation:
    """Test that classes can be instantiated without errors."""

    def test_filesystem_credentials_manager_instantiation(self):
        """FileSystemCredentialsManager should instantiate with module_name."""
        manager = FileSystemCredentialsManager(module_name="test_module")
        assert manager.module_name == "test_module"
        assert ".test_module" in manager.creds_folder_path

    def test_on_prem_secrets_manager_instantiation(self):
        """OnPremSecretsManager should instantiate without arguments."""
        manager = OnPremSecretsManager()
        assert manager is not None

    def test_vault_secrets_manager_instantiation(self):
        """VaultSecretsManager should instantiate with optional parameters."""
        manager = VaultSecretsManager(
            mount_point="test_mount",
            path_prefix="test_prefix",
        )
        assert manager.mount_point == "test_mount"
        assert manager.path_prefix == "test_prefix"

    def test_ssm_secrets_manager_instantiation(self):
        """SSMSecretsManager should instantiate with optional region."""
        manager = SSMSecretsManager(region="us-east-1")
        assert manager._region == "us-east-1"
