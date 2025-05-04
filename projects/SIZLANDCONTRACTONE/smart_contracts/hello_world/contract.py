from algopy import Account, ARC4Contract, Asset, BoxMap, Global, Txn, arc4, itxn
from algopy.arc4 import Struct


class UserAllocation(Struct):
    total_allocation: arc4.UInt64
    claimed_amount: arc4.UInt64
    start_time: arc4.UInt64
    cliff_time: arc4.UInt64
    vesting_period: arc4.UInt64
    last_claim_time: arc4.UInt64


class SizlandVestingContract(ARC4Contract):
    # Define state variables for vesting  parameters
    # For example: beneficiary, total amount, vesting period, etc.

    def __init__(self) -> None:
        # Initialize your contract state
        # This will be executed once on deployment
        self.asa = Asset()
        self.allocations = BoxMap(Account, UserAllocation, key_prefix="")

    @arc4.abimethod
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into a ASA
        assert Txn.sender == Global.creator_address, "Only creator can opt in to ASA"
        # Verify a ASA hasn't already been opted into
        assert self.asa.id == 2905622564, "ASA already opted in"
        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        itxn.AssetTransfer(
            asset_receiver=Global.current_application_address,
            xfer_asset=asset,
        ).submit()

    @arc4.abimethod
    def set_allocation(
        self,
        beneficiary: Account,
        total_allocation: arc4.UInt64,
        start_time: arc4.UInt64,
        cliff_time: arc4.UInt64,
        vesting_period: arc4.UInt64,
    ) -> None:
        assert (
            Txn.sender == Global.creator_address
        ), "Only the creator can call this method"
        self.allocations[beneficiary] = UserAllocation(
            total_allocation=total_allocation,
            claimed_amount=arc4.UInt64(0),
            start_time=start_time,
            cliff_time=cliff_time,
            vesting_period=vesting_period,
            last_claim_time=arc4.UInt64(0),
        )

    @arc4.abimethod
    def claim(self) -> None:
        current_time = arc4.UInt64(Global.latest_timestamp)
        sender = Txn.sender

        # Check allocation exists
        assert sender in self.allocations, "No allocation found"
        allocation = self.allocations[sender].copy()  # safe struct access

        # Enforce cliff
        assert current_time >= allocation.cliff_time, "Cliff not reached"
