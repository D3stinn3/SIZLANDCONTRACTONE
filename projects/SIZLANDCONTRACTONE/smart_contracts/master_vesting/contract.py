from algopy import Account, ARC4Contract, Asset, BoxMap, Global, Txn, arc4, itxn


class MasterVesting(ARC4Contract):
    def __init__(self) -> None:
        # Track deployed vesting contracts
        self.vesting_contracts = BoxMap(arc4.UInt64, Account, key_prefix="contracts")
        self.contract_count = arc4.UInt64(0)
        self.asa = Asset()

    @arc4.abimethod
    def register_vesting_contract(self, contract_address: Account) -> None:
        # Only creator can register new vesting contracts
        assert (
            Txn.sender == Global.creator_address
        ), "Only creator can register vesting contracts"

        # Store the contract address
        contract_id = self.contract_count.native
        self.vesting_contracts[arc4.UInt64(contract_id)] = contract_address

        # Increment counter
        self.contract_count = arc4.UInt64(contract_id + 1)

    @arc4.abimethod
    def get_vesting_contract(self, index: arc4.UInt64) -> Account:
        assert index.native < self.contract_count.native, "Invalid contract index"
        return self.vesting_contracts[index]

    @arc4.abimethod
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into an ASA
        assert Txn.sender == Global.creator_address, "Only creator can opt in to ASA"

        # Verify an ASA hasn't already been opted into
        assert self.asa.id == 0, "ASA already opted in"

        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        itxn.AssetTransfer(
            asset_receiver=Global.current_application_address,
            xfer_asset=asset,
        ).submit()
